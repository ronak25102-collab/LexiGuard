"""Adapters for a pinned-model evaluation against real Aura and persistent Chroma."""

from langchain_core.embeddings import Embeddings
from langchain_core.messages import AIMessage

from lexiguard.evaluation.focused_ablation import GoogleCalls
from lexiguard.evaluation.focused_ablation import digest, write_json
from lexiguard.config import get_settings
import json
import time
import threading
import re
from pathlib import Path


class CachedGoogleEmbeddings(Embeddings):
    def __init__(self, calls: GoogleCalls):
        self.calls = calls

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self.calls.embed(texts).tolist()

    def embed_query(self, text: str) -> list[float]:
        return self.calls.embed([text], query=True)[0].tolist()


class PinnedGoogleChat:
    def __init__(self, calls: GoogleCalls):
        self.calls = calls

    def invoke(self, prompt) -> AIMessage:
        value = prompt if isinstance(prompt, str) else prompt.to_string()
        return AIMessage(content=self.calls.text(value))


class CachedCompatibleCalls:
    """Cache exact prompts and complete responses, isolated by endpoint and model."""

    def __init__(self, output: Path, provider: str, model: str, require_json: bool = False):
        from openai import OpenAI
        settings = get_settings()
        self.model = model
        self.provider = provider
        self.require_json = require_json
        self.key = getattr(settings, provider + "_api_key")
        self.endpoint = getattr(settings, provider + "_base_url")
        self.client = OpenAI(api_key=self.key, base_url=self.endpoint, timeout=90, max_retries=0)
        self.cache = output / "cache"
        self.cache.mkdir(parents=True, exist_ok=True)
        self._rate_lock = threading.Lock()
        self._next_request = 0.0

    def text(self, prompt: str, model: str | None = None) -> str:
        model = model or self.model
        extra = {"chat_template_kwargs": {"enable_thinking": False}} if (
            self.provider == "nvidia" and "nemotron-3-" in model) else {}
        request = {"model": model, "temperature": 0, "max_tokens": 8192,
                   "messages": [{"role": "user", "content": prompt}], "extra_body": extra}
        path = self.cache / (digest([self.endpoint, request]) + ".json")
        if path.exists():
            cached = json.loads(path.read_text("utf-8"))
            try:
                value = self._validate(cached["text"])
                if value != cached["text"]:
                    write_json(self.cache.parent / "cache_failures" / f"{path.stem}.syntax_original.json", cached)
                    cached.update(original_text=cached["text"], text=value,
                                  format_repair="single missing JSON member comma")
                    write_json(path, cached)
                return value
            except json.JSONDecodeError:
                write_json(self.cache.parent / "cache_failures" / path.name, cached)
                path.unlink()
        for attempt in range(4):
            try:
                with self._rate_lock:
                    time.sleep(max(0, self._next_request - time.monotonic()))
                    interval = 1.8 if self.provider == "nvidia" else 1.1
                    self._next_request = time.monotonic() + interval
                response = self.client.chat.completions.create(**request)
                choice = response.choices[0]
                if choice.finish_reason != "stop" or not choice.message.content:
                    raise RuntimeError("Model returned empty or incomplete output")
                value = choice.message.content.strip()
                record = {"provider": self.provider, "endpoint": self.endpoint,
                           "request": request, "response_model": response.model,
                           "text": value, "usage": response.usage.model_dump() if response.usage else None,
                           "finish_reason": choice.finish_reason}
                try:
                    normalized = self._validate(value)
                    if normalized != value:
                        write_json(self.cache.parent / "cache_failures" / f"{path.stem}.syntax_original.json", record)
                        record.update(original_text=value, text=normalized,
                                      format_repair="single missing JSON member comma")
                        value = normalized
                except json.JSONDecodeError:
                    write_json(self.cache.parent / "cache_failures" / f"{path.stem}.{attempt}.json", record)
                    raise
                write_json(path, record)
                return value
            except Exception as error:
                status = getattr(error, "status_code", None)
                transient = isinstance(error, json.JSONDecodeError) or status in {408, 429, 500, 502, 503, 504} or (
                    type(error).__name__ in {"APITimeoutError", "APIConnectionError"})
                if not transient or attempt == 3:
                    raise
                headers = getattr(getattr(error, "response", None), "headers", {})
                delay = min(60, max(2 ** (attempt + 1), float(headers.get("retry-after", 0))))
                print("PROVIDER_RETRY", self.provider, status, delay, flush=True)
                time.sleep(delay)
        raise RuntimeError("Retry exhausted")

    def _validate(self, text: str) -> str:
        if self.require_json:
            value = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            fixed = repair_single_member_comma(value)
            return fixed if fixed != value else text
        return text


def repair_single_member_comma(text: str) -> str:
    """Repair one unambiguous member delimiter, without changing any verdict/value."""
    try:
        json.loads(text)
        return text
    except json.JSONDecodeError as error:
        if (error.msg != "Expecting ',' delimiter" or
                not text[:error.pos].rstrip().endswith('"') or
                not re.match(r'"(?:[^"\\]|\\.)*"\s*:', text[error.pos:])):
            raise
        repaired = text[:error.pos] + "," + text[error.pos:]
        json.loads(repaired)  # Do not complete tokens, infer values or accept further damage.
        return repaired
