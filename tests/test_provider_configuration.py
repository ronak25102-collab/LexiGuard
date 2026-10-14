"""Generation failover must preserve the indexed embedding model and its credentials."""

from unittest.mock import patch

import pytest

from lexiguard.config import LLMProvider, Settings
from lexiguard.ingestion.vector_store import get_embeddings, get_vectorstore


def test_gateway_generation_keeps_google_embedding_space():
    settings = Settings(_env_file=None, llm_provider="codecraft", embedding_provider="google",
                        codecraft_api_key="gateway-test", google_api_key="embedding-test")
    with patch("lexiguard.ingestion.vector_store.get_settings", return_value=settings), \
         patch("langchain_google_genai.GoogleGenerativeAIEmbeddings") as embeddings, \
         patch("lexiguard.ingestion.vector_store.Chroma") as store:
        get_vectorstore()
    assert embeddings.call_args.kwargs["api_key"] == "embedding-test"
    assert embeddings.call_args.kwargs["model"] == "models/gemini-embedding-001"
    assert embeddings.call_args.kwargs["output_dimensionality"] == 768
    assert store.call_args.kwargs["collection_name"] == "contracts_gemini_embedding_001_768"
    assert store.call_args.kwargs["persist_directory"].endswith("gemini_embedding_001_768")


def test_gateway_requires_an_explicit_embedding_provider():
    settings = Settings(_env_file=None, llm_provider="codecraft", embedding_provider=None)
    with patch("lexiguard.ingestion.vector_store.get_settings", return_value=settings), \
         pytest.raises(ValueError, match="EMBEDDING_PROVIDER"):
        get_embeddings()


def test_existing_provider_defaults_remain_compatible():
    settings = Settings(_env_file=None, llm_provider="nvidia", embedding_provider=None)
    assert settings.effective_embedding_provider == LLMProvider.NVIDIA


def test_query_and_document_vectors_use_the_same_unit_length():
    from unittest.mock import MagicMock
    from lexiguard.ingestion.vector_store import NormalizedEmbeddings
    underlying = MagicMock()
    underlying.embed_documents.return_value = [[3.0, 4.0], [0.0, 0.0]]
    underlying.embed_query.return_value = [3.0, 4.0]
    embeddings = NormalizedEmbeddings(underlying)
    assert embeddings.embed_query("law") == [0.6, 0.8]
    assert embeddings.embed_documents(["law", ""]) == [[0.6, 0.8], [0.0, 0.0]]


def test_gateway_extraction_works_without_forced_tool_choice():
    import json
    import httpx
    from openai import OpenAI
    from lexiguard.ingestion.extractor import _extract_with_openai, PartyResolutionResult
    settings = Settings(_env_file=None, llm_provider="codecraft", codecraft_api_key="test")
    def reply(request):
        body = json.loads(request.content)
        if body.get("tool_choice") is not None and body["tool_choice"] != "auto":
            return httpx.Response(400, json={"error": {"message": "Unsupported forced tool choice"}})
        return httpx.Response(200, json={"id": "mock", "model": "test", "object": "chat.completion",
            "created": 0, "choices": [{"index": 0, "finish_reason": "stop", "message": {
                "role": "assistant", "content": json.dumps({"resolved_parties": [
                    {"name": "Alpha", "role": "Client", "jurisdiction": None}]})}}]})
    class TestClient(OpenAI):
        def __init__(self, *args, **kwargs):
            kwargs["http_client"] = httpx.Client(transport=httpx.MockTransport(reply))
            super().__init__(*args, **kwargs)
    with patch("lexiguard.ingestion.extractor.get_settings", return_value=settings), \
         patch("openai.OpenAI", TestClient):
        result = _extract_with_openai("Alpha is the Client.", "Extract parties.", PartyResolutionResult)
    assert result.resolved_parties[0].name == "Alpha"


def test_malformed_judge_json_is_preserved_and_retried_with_identical_inputs(tmp_path):
    from types import SimpleNamespace
    from unittest.mock import MagicMock
    from lexiguard.evaluation.live_ablation import CachedCompatibleCalls
    settings = Settings(_env_file=None, nvidia_api_key="test")
    client = MagicMock()
    def response(value):
        return SimpleNamespace(model="test", usage=None, choices=[SimpleNamespace(
            finish_reason="stop", message=SimpleNamespace(content=value))])
    client.chat.completions.create.side_effect = [response('{"invalid"'), response('{"valid":true}')]
    with patch("lexiguard.evaluation.live_ablation.get_settings", return_value=settings), \
         patch("openai.OpenAI", return_value=client), \
         patch("lexiguard.evaluation.live_ablation.time.sleep"):
        calls = CachedCompatibleCalls(tmp_path, "nvidia", "test", require_json=True)
        assert calls.text("Return JSON") == '{"valid":true}'
        assert calls.text("Return JSON") == '{"valid":true}'
    assert client.chat.completions.create.call_count == 2
    assert client.chat.completions.create.call_args_list[0] == client.chat.completions.create.call_args_list[1]
    assert len(list((tmp_path / "cache_failures").glob("*.json"))) == 1


def test_json_member_comma_repair_preserves_verdict_and_rejects_missing_values():
    import json
    from lexiguard.evaluation.live_ablation import repair_single_member_comma
    raw = '{"statement":"No provision retrieved."\n "reason":"Nothing relevant." ,"verdict":0}'
    fixed = repair_single_member_comma(raw)
    assert fixed.replace(',', '', 1) == raw
    assert json.loads(fixed) == {"statement": "No provision retrieved.",
                               "reason": "Nothing relevant.", "verdict": 0}
    with pytest.raises(json.JSONDecodeError):
        repair_single_member_comma('{"statement":"No provision retrieved.","verdict":')
