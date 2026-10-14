"""Check experiment integrity without model calls or external services."""
from lexiguard.evaluation.focused_ablation import (
    CONTEXT_CHARS, VARIANTS, cap_context, neighbors, parse_msa, summarize,
)


def test_incoming_override_is_retrieved_from_original_clause():
    clauses = {"7.1": "general cap", "7.2": "confidentiality exception"}
    assert neighbors(clauses, [("7.2", "7.1", "EXCLUDES")], "7.1") == ["7.2"]


def test_unresolved_graph_edges_do_not_invent_source_clauses():
    assert neighbors({"13.1": "indemnity"}, [("13.4", "13.1", "MODIFIES")], "13.1") == []


def test_context_budget_and_duplicate_elimination_apply_to_all_retrieval_sources():
    docs = [{"text": "a" * 2000}, {"text": "a" * 2000},
            {"text": "b" * 2000}, {"text": "c" * 2000}, {"text": "d"}]
    selected = cap_context(docs)
    assert len(selected) == 3
    assert sum(len(doc["text"]) for doc in selected) == CONTEXT_CHARS


def test_incomplete_cases_are_excluded_from_every_variant_average():
    rows = [{"case_id": "complete", "variant": v, "faithfulness": .5,
             "context_precision": .75, "seconds": 1, "rewrites": 0} for v in VARIANTS]
    rows += [{"case_id": "failed", "variant": v, "faithfulness": 1,
              "context_precision": 1, "seconds": 1, "rewrites": 0} for v in VARIANTS[:-1]]
    rows.append({"case_id": "failed", "variant": VARIANTS[-1], "error": "provider failure"})
    summary = summarize(rows)
    assert summary["paired_case_ids"] == ["complete"]
    assert all(r["faithfulness"] == .5 and r["n"] == 1 for r in summary["variants"].values())


def test_demo_parser_keeps_exception_text_with_its_clause():
    text = "* **3.2 Penalty:** 1.5%. * **3.3 Exception:** No penalty.\n* (a) client delay\n---\n* **4.1 IP:** work for hire"
    clauses = parse_msa(text)
    assert "client delay" in clauses["3.3"]
    assert "4.1" not in clauses["3.3"]
