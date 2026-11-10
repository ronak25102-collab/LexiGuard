"""Bounded CodeCraft key/model failover shared by chat and extraction."""

import logging
import threading
import time
from functools import lru_cache

from langchain_openai import ChatOpenAI
from openai import APIConnectionError, APIStatusError
from pydantic import PrivateAttr

logger = logging.getLogger(__name__)


def _provider_error(error):
    """Instructor may wrap the original SDK error after a validation attempt."""
    seen = set()
    while error is not None and id(error) not in seen:
        seen.add(id(error))
        if isinstance(error, (APIStatusError, APIConnectionError)):
            return error
        error = error.__cause__ or error.__context__
    return None


class CodeCraftPool:
    def __init__(self, keys, models):
        self.keys = tuple(keys)
        self.models = tuple(models)
        self._lock = threading.Lock()
        self._cooldowns = {}
        self._preferred = (models[0], 0)

    def call(self, action):
        with self._lock:
            now = time.monotonic()
            preferred_model, preferred_key = self._preferred
            models = sorted(self.models, key=lambda model: model != preferred_model)
            indices = sorted(range(len(self.keys)), key=lambda index: index != preferred_key)
            routes = [(model, index) for model in models for index in indices
                      if self._cooldowns.get(('key', index), 0) <= now
                      and self._cooldowns.get((model, index), 0) <= now]
        if not routes:
            raise RuntimeError("CodeCraft keys are temporarily unavailable; please try again later.")
        last_error = None
        unavailable_models = set()
        failed_keys = set()
        for model, index in routes:
            if model in unavailable_models or index in failed_keys:
                continue
            try:
                result = action(self.keys[index], model)
                with self._lock:
                    self._preferred = (model, index)
                return result
            except Exception as error:
                provider_error = _provider_error(error)
                if provider_error is None:
                    raise
                status = getattr(provider_error, 'status_code', None)
                if status not in (401, 402, 403, 404, 408, 429) and not (
                    status is None or status >= 500
                ):
                    raise
                last_error = provider_error
                cooldown = 30.0
                if status in (401, 402, 403, 429):
                    failed_keys.add(index)
                    cooldown = 300.0 if status in (401, 402, 403) else 60.0
                    try:
                        cooldown = max(cooldown, float(provider_error.response.headers.get('retry-after', 0)))
                    except (ValueError, AttributeError):
                        pass
                    scope = ('key', index)
                else:
                    scope = (model, index)
                if status == 404:
                    unavailable_models.add(model)
                with self._lock:
                    self._cooldowns[scope] = time.monotonic() + cooldown
                    if status == 404:
                        for key_index in range(len(self.keys)):
                            self._cooldowns[(model, key_index)] = time.monotonic() + 300
                # No API key, request body or provider error body enters the log.
                logger.warning("CodeCraft model %s, key slot %d failed (%s); trying fallback",
                               model, index + 1, status or type(provider_error).__name__)
        if last_error is not None:
            raise last_error
        raise RuntimeError("CodeCraft has no available model/key combination.")


@lru_cache(maxsize=8)
def _pool(keys, models):
    return CodeCraftPool(keys, models)


def get_codecraft_pool(settings):
    models = tuple(dict.fromkeys([settings.codecraft_model, *settings.codecraft_fallback_models]))
    return _pool(tuple(settings.codecraft_keys), models)


@lru_cache(maxsize=32)
def _chat_client(model, key, base_url, temperature, max_tokens, timeout):
    return ChatOpenAI(model=model, api_key=key, base_url=base_url, temperature=temperature,
                      max_tokens=max_tokens, timeout=timeout, max_retries=0)


class CodeCraftChatOpenAI(ChatOpenAI):
    _settings = PrivateAttr()

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        settings = self._settings

        def generate(key, model):
            client = _chat_client(model, key, settings.codecraft_base_url, self.temperature,
                                  self.max_tokens, settings.codecraft_timeout)
            return client._generate(messages, stop=stop, run_manager=run_manager, **kwargs)

        return get_codecraft_pool(settings).call(generate)

    async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
        # Reuse the same bounded failover/cooldown logic without blocking the event loop.
        import asyncio
        return await asyncio.to_thread(self._generate, messages, stop, None, **kwargs)


def get_codecraft_llm(settings):
    llm = CodeCraftChatOpenAI(model=settings.codecraft_model, api_key=settings.active_api_key,
                             base_url=settings.codecraft_base_url, temperature=0,
                             max_tokens=settings.codecraft_max_tokens,
                             timeout=settings.codecraft_timeout, max_retries=0)
    llm._settings = settings
    return llm
