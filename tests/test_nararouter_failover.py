"""Real SDK errors exercise NaraRouter key/model routing without making network requests."""

from unittest.mock import patch

import httpx
import pytest
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from openai import APIConnectionError, APIStatusError

from lexiguard.config import Settings
from lexiguard.providers.nararouter import NaraRouterPool, get_nararouter_llm


def failure(status, headers=None):
    response = httpx.Response(status, headers=headers, request=httpx.Request('POST', 'https://example.test'))
    return APIStatusError('Provider failure', response=response, body=None)


def test_rotates_keys_and_reuses_successful_key_without_exposing_keys(caplog):
    pool = NaraRouterPool(['first-private-key', 'second-private-key'], ['fast'])
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
    pool = NaraRouterPool(['one', 'two'], ['missing', 'supported'])
    calls = []

    def request(key, model):
        calls.append((key, model))
        if model == 'missing':
            raise failure(404)
        return 'ok'

    assert pool.call(request) == 'ok'
    assert ('one', 'supported') in calls
    assert ('two', 'missing') not in calls


def test_rate_limited_keys_respect_retry_after_and_do_not_retry_other_models():
    pool = NaraRouterPool(['exhausted', 'available'], ['primary', 'fallback'])
    calls = []

    def request(key, model):
        calls.append((key, model))
        if key == 'exhausted':
            raise failure(429, headers={'retry-after': '120'})
        return 'ok'

    assert pool.call(request) == 'ok'
    assert calls[0] == ('exhausted', 'primary')
    assert ('exhausted', 'fallback') not in calls
    assert calls[1] == ('available', 'primary')


@pytest.mark.parametrize('status', [400, 422])
def test_invalid_requests_are_not_retried_with_other_keys(status):
    pool = NaraRouterPool(['one', 'two'], ['fast'])
    calls = []

    def request(key, model):
        calls.append((key, model))
        raise failure(status)

    with pytest.raises(APIStatusError) as exc_info:
        pool.call(request)
    assert exc_info.value.status_code == status
    assert calls == [('one', 'fast')]


def test_connection_failure_moves_to_another_key():
    pool = NaraRouterPool(['one', 'two'], ['fast'])
    calls = []

    def request(key, _):
        calls.append(key)
        if key == 'one':
            raise APIConnectionError(request=httpx.Request('POST', 'https://example.test'))
        return 'ok'

    assert pool.call(request) == 'ok'
    assert calls == ['one', 'two']


def test_explicit_pool_overrides_legacy_key_and_redacts_settings():
    settings = Settings(_env_file=None, llm_provider='nararouter', nararouter_api_key='old-private',
                        nararouter_api_keys=['new-private', 'new-private', 'next-private'])
    assert settings.nararouter_keys == ['new-private', 'next-private']
    assert settings.active_api_key == 'new-private'
    assert 'new-private' not in repr(settings)
    assert 'old-private' not in repr(settings)
