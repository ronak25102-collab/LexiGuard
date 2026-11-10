"""Real SDK errors exercise the key/model routing without making network requests."""

from unittest.mock import patch

import httpx
import pytest
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from openai import APIConnectionError, APIStatusError

from lexiguard.config import Settings
from lexiguard.providers.codecraft import CodeCraftPool, get_codecraft_llm


def failure(status, headers=None):
    response = httpx.Response(status, headers=headers, request=httpx.Request('POST', 'https://example.test'))
    return APIStatusError('Provider failure', response=response, body=None)


def test_rotates_keys_and_reuses_successful_key_without_exposing_keys(caplog):
    pool = CodeCraftPool(['first-private-key', 'second-private-key'], ['fast'])
    calls = []

    def request(key, model):
        calls.append((key, model))
        if key == 'first-private-key':
            raise failure(401)
        return 'ok'

    assert pool.call(request) == 'ok'
    assert pool.call(request) == 'ok'
    assert [key for key, _ in calls] == ['first-private-key', 'second-private-key', 'second-private-key']
    assert 'first-private-key' not in caplog.text
    assert 'second-private-key' not in caplog.text


def test_unknown_model_skips_other_keys_and_uses_model_fallback():
    pool = CodeCraftPool(['first', 'second'], ['unavailable', 'backup'])
    calls = []

    def request(key, model):
        calls.append((key, model))
        if model == 'unavailable':
            raise failure(404)
        return 'ok'

    assert pool.call(request) == 'ok'
    assert calls == [('first', 'unavailable'), ('first', 'backup')]


def test_rate_limited_keys_respect_retry_after_and_do_not_retry_other_models():
    pool = CodeCraftPool(['one', 'two'], ['fast', 'backup'])
    calls = []

    def request(key, model):
        calls.append((key, model))
        raise failure(429, {'retry-after': '120'})

    with patch('lexiguard.providers.codecraft.time.monotonic', return_value=10):
        with pytest.raises(APIStatusError):
            pool.call(request)
        assert pool._cooldowns[('key', 0)] == 130
        with pytest.raises(RuntimeError, match='temporarily unavailable'):
            pool.call(request)
    assert len(calls) == 2


@pytest.mark.parametrize('status', [400, 422])
def test_invalid_requests_are_not_retried_with_other_keys(status):
    pool = CodeCraftPool(['one', 'two'], ['fast', 'backup'])
    with patch('builtins.print'):
        with pytest.raises(APIStatusError) as caught:
            pool.call(lambda *_: (_ for _ in ()).throw(failure(status)))
    assert caught.value.status_code == status
    assert not pool._cooldowns


def test_connection_failure_moves_to_another_key():
    pool = CodeCraftPool(['one', 'two'], ['fast'])
    calls = []

    def request(key, _):
        calls.append(key)
        if key == 'one':
            raise APIConnectionError(request=httpx.Request('POST', 'https://example.test'))
        return 'ok'

    assert pool.call(request) == 'ok'
    assert calls == ['one', 'two']


def test_explicit_pool_overrides_legacy_key_and_redacts_settings():
    settings = Settings(_env_file=None, llm_provider='codecraft', codecraft_api_key='old-private',
                        codecraft_api_keys=['new-private', 'new-private', 'next-private'])
    assert settings.codecraft_keys == ['new-private', 'next-private']
    assert settings.active_api_key == 'new-private'
    assert 'new-private' not in repr(settings)
    assert 'old-private' not in repr(settings)


@pytest.mark.asyncio
async def test_async_langchain_calls_use_the_same_failover():
    settings = Settings(_env_file=None, llm_provider='codecraft', codecraft_api_keys=['async1', 'async2'])
    output = ChatResult(generations=[ChatGeneration(message=AIMessage(content='grounded answer'))])
    with patch('langchain_openai.ChatOpenAI._generate', side_effect=[failure(401), output]) as generate:
        answer = await get_codecraft_llm(settings).ainvoke('Question')
    assert answer.content == 'grounded answer'
    assert generate.call_count == 2


def test_wrapped_instructor_provider_error_still_rotates_key():
    pool = CodeCraftPool(['one', 'two'], ['fast'])

    def request(key, _):
        if key == 'one':
            try:
                raise failure(402)
            except APIStatusError as cause:
                raise RuntimeError('Structured extraction failed') from cause
        return 'ok'

    assert pool.call(request) == 'ok'
