"""Regression checks for evidence loss, scope leakage and unsupported answers."""

import hashlib
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from langgraph.graph import END, START, StateGraph

from lexiguard.agent.nodes import generate_with_disclaimer, retrieve, rewrite_query
from lexiguard.agent.retrieval import rank_candidates, select_context, source_aliases
from lexiguard.agent.state import GraphState


def test_heading_finds_law_clause_despite_party_name_distractors():
    docs = [
        {"title": "Preamble", "text": "Alpha and Beta enter this commercial agreement."},
        {"title": "Governing Law", "text": "This agreement is interpreted under Nevada law."},
    ]
    assert rank_candidates("What law governs the Alpha/Beta agreement?", docs)[0] == docs[1]


def test_fusion_retains_semantic_background_and_linked_exception():
    graph = [
        {"kind": "graph", "contract_id": "a", "section": "7.1", "title": "Liability cap",
         "text": "Liability is capped at fees paid."},
        {"kind": "graph", "contract_id": "a", "section": "7.2", "linked_to": "7.1",
         "title": "Exception", "text": "The cap excludes confidentiality breaches."},
        {"kind": "graph", "contract_id": "a", "section": "8", "text": "Unrelated provision."},
    ]
    semantic = [{"kind": "semantic", "contract_id": "a", "section": None,
                 "text": "Alpha is the client; Beta is the vendor. Liability rules follow."}]
    docs = select_context("What liability cap applies?", graph, semantic)
    assert {d["kind"] for d in docs} == {"graph", "semantic"}
    assert {d["section"] for d in docs if d["kind"] == "graph"} == {"7.1", "7.2"}
    assert sum(len(d["text"]) for d in docs) <= 4500


def test_long_clause_tail_is_retrieved_without_discarding_semantic_evidence():
    from lexiguard.agent.retrieval import source_window
    doc = {"text": "Unrelated background. " * 250 + "Governing law: California."}
    excerpt, start = source_window("What is the governing law?", doc, 1000)
    assert "California" in excerpt
    assert excerpt == doc["text"][start:start + len(excerpt)]


def test_context_budget_retains_a_complete_long_obligation_when_it_fits():
    body = "Audit procedure. " * 100 + "The payor pays within fifteen days."
    docs = select_context("What audit payment deadline applies?",
                          [{"kind": "graph", "section": "4", "text": body}],
                          [{"kind": "semantic", "text": "Audits require a written invoice."}])
    assert any("fifteen days" in d["text"] for d in docs)
    assert any(d["kind"] == "semantic" for d in docs)
    assert sum(len(d["text"]) for d in docs) <= 4500


def test_aliases_match_uploaded_ids_to_graph_hashes():
    source = "uploaded_contract_123"
    cid = hashlib.sha256(source.encode()).hexdigest()
    assert cid in source_aliases({"contract_id": cid, "source_file": source})
    assert source in source_aliases({"contract_id": cid, "source_file": source})


def test_initial_term_facet_survives_a_combined_term_and_notice_question():
    from lexiguard.agent.retrieval import topic_terms
    terms = topic_terms(
        "How long is the initial term, how does renewal work, and what notice ends it?"
    )
    assert "initial" in terms and "effective date" in terms
    assert "renewal" in terms


def test_neo4j_failure_does_not_disable_scoped_semantic_retrieval():
    store = MagicMock()
    store.similarity_search.return_value = [SimpleNamespace(
        page_content="Governing law: Nevada.", metadata={"contract_id": "chosen"})]
    with patch("lexiguard.agent.nodes._get_neo4j_client", side_effect=OSError("offline")), \
         patch("lexiguard.agent.nodes.get_vectorstore", return_value=store):
        result = retrieve({"question": "What is the governing law?", "contract_filter": "chosen"})
    assert "Nevada" in result["graph_context"][0]
    assert store.similarity_search.call_args.kwargs["filter"] == {
        "contract_id": {"$in": ["chosen"]}}
    assert "graph_unavailable" in result["retrieval_errors"]


def test_failed_scope_does_not_fall_back_to_other_contracts(tmp_path):
    from lexiguard.agent.nodes import _local_source_candidates
    (tmp_path / "other.md").write_text("# Other Contract\nGoverning law: Nevada.")
    with patch("lexiguard.config.PARSED_DATA_DIR", tmp_path), \
         patch("lexiguard.config.DATA_DIR", tmp_path):
        assert _local_source_candidates("governing law", "missing-contract", []) == []


def test_query_rewrite_preserves_original_scenario():
    llm = MagicMock()
    llm.invoke.return_value.content = "late delivery exemption"
    state = {"question": "What happens to the $40,000 milestone?", "retry_count": 0}
    with patch("lexiguard.agent.nodes.get_llm", return_value=llm):
        result = rewrite_query(state)
    assert "question" not in result
    assert state["question"] == "What happens to the $40,000 milestone?"
    assert result["retrieval_question"] == "late delivery exemption"


def test_named_party_queries_do_not_use_an_unscoped_vector_search():
    client = MagicMock()
    client.run_query.return_value = []
    store = MagicMock()
    with patch("lexiguard.agent.nodes._get_neo4j_client", return_value=client), \
         patch("lexiguard.agent.nodes.get_vectorstore", return_value=store), \
         patch("lexiguard.agent.nodes._local_source_candidates", return_value=[]):
        result = retrieve({"question": "What law governs Alpha's agreement?",
                           "party_filter": ["Alpha"], "contract_filter": None})
    store.similarity_search.assert_not_called()
    assert client.run_query.call_args.args[1]["party_names"] == ["Alpha"]
    assert result["graph_context"] == []


def test_schema_binding_precedes_google_fallback_composition():
    from lexiguard.graph.schema import ExtractionData
    from lexiguard.ingestion.extractor import _extract_with_google
    class TypedRunnable:
        def with_fallbacks(self, other):
            assert isinstance(other[0], TypedRunnable)
            return self

        def invoke(self, prompt):
            return ExtractionData(title="Test")

    class ChatModel:
        def __init__(self, **kwargs):
            pass

        def with_structured_output(self, schema):
            assert schema is ExtractionData
            return TypedRunnable()

    with patch("langchain_google_genai.ChatGoogleGenerativeAI", ChatModel):
        assert _extract_with_google("text", "prompt").title == "Test"


def test_retry_evidence_replaces_stale_context():
    graph = StateGraph(GraphState)
    graph.add_node("replace", lambda state: {"graph_context": ["new evidence"]})
    graph.add_edge(START, "replace")
    graph.add_edge("replace", END)
    result = graph.compile().invoke({"question": "test", "graph_context": ["stale evidence"]})
    assert result["graph_context"] == ["new evidence"]


def test_insufficient_evidence_abstains_without_calling_model():
    with patch("lexiguard.agent.nodes.get_llm") as llm:
        result = generate_with_disclaimer({"question": "governing law", "graph_context": []})
    llm.assert_not_called()
    assert "retrieve enough evidence" in result["generation"]
    assert "contract is silent" not in result["generation"]


def test_provider_failure_returns_error_instead_of_fabricated_clauses():
    from lexiguard.api.main import process_query
    from lexiguard.api.models import QueryRequest
    with patch("lexiguard.api.main.run_agent", side_effect=RuntimeError("429 quota exceeded")):
        with pytest.raises(HTTPException) as error:
            process_query(QueryRequest(question="What is the governing law?"))
    assert error.value.status_code == 503


def test_example_evaluation_scores_are_not_served_as_real_metrics(tmp_path, monkeypatch):
    import json

    from lexiguard.api.main import get_evaluation_results
    monkeypatch.chdir(tmp_path)
    (tmp_path / "evaluation_results.json").write_text(json.dumps([
        {"full_question": "Sample Question 1", "faithfulness": .95}]))
    assert get_evaluation_results()["data"] is None


def test_citations_use_clause_number_instead_of_contract_hash():
    from lexiguard.api.main import process_query
    from lexiguard.api.models import QueryRequest
    with patch("lexiguard.api.main.run_agent", return_value={
        "answer": "Nevada", "sources": [{"contract_id": "long-hash", "clause_number": "15.3",
        "clause_text": "Nevada law", "contract_title": "Test"}]}):
        response = process_query(QueryRequest(question="governing law"))
    assert response.sources[0].clause_number == "15.3"


def test_saved_measured_evaluation_preserves_provenance(tmp_path, monkeypatch):
    import json
    from lexiguard.api.main import get_evaluation_results
    monkeypatch.chdir(tmp_path)
    data = {"data": [{"question": "L01", "faithfulness": 0.9, "context_precision": 0.8}],
            "available_metrics": ["faithfulness", "context_precision"],
            "metadata": {"live_aura": True, "variant_label": "Hybrid + CRAG"}}
    (tmp_path / "evaluation_results.json").write_text(json.dumps(data), "utf-8")
    assert get_evaluation_results() == data


def test_crag_can_restore_complete_semantic_evidence_displaced_by_graph():
    from lexiguard.agent.nodes import grade_relevance
    llm = MagicMock()
    llm.invoke.return_value.content = '{"choice":"semantic","relevance":"relevant","reason":"Complete renewal provision."}'
    semantic = [{"text": "Automatically renews for one year unless 30 days notice is given."}]
    hybrid = [{"text": "Notice that the agreement will not be renewed."}]
    state = {"question": "What renewal term and notice apply?", "documents": hybrid,
             "graph_context": [hybrid[0]["text"]], "semantic_documents": semantic}
    with patch("lexiguard.agent.nodes.get_llm", return_value=llm):
        result = grade_relevance(state)
    assert result["documents"] == semantic
    assert result["graph_context"] == [semantic[0]["text"]]
    assert result["relevance_score"] == "relevant"
    assert "Notice that" in llm.invoke.call_args.args[0]
    assert "Automatically renews" in llm.invoke.call_args.args[0]


def test_invalid_evidence_choice_cannot_accept_a_degraded_graph_result():
    from lexiguard.agent.nodes import grade_relevance
    llm = MagicMock()
    llm.invoke.return_value.content = '{"choice":"invented","relevance":"relevant"}'
    semantic = [{"text": "Complete source provision."}]
    with patch("lexiguard.agent.nodes.get_llm", return_value=llm):
        result = grade_relevance({"question": "What applies?", "documents": [],
                                  "semantic_documents": semantic})
    assert result["relevance_score"] == "irrelevant"
    assert result["documents"] == semantic


def test_ingestion_metadata_uses_same_id_as_graph_and_stable_chunk_ids():
    from lexiguard.ingestion.vector_store import add_contract_to_vectorstore
    store = MagicMock()
    with patch("lexiguard.ingestion.vector_store.get_vectorstore", return_value=store):
        add_contract_to_vectorstore("source_123", "# Demo Contract\nPayment is Net-30.")
        add_contract_to_vectorstore("source_123", "# Demo Contract\nPayment is Net-30.")
    kwargs = store.add_texts.call_args.kwargs
    assert kwargs["metadatas"][0]["contract_id"] == hashlib.sha256(b"source_123").hexdigest()
    assert store.add_texts.call_args_list[0].kwargs["ids"] == kwargs["ids"]
