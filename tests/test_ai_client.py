"""Tests for model-client timeout building and error humanization."""

from __future__ import annotations

from unittest.mock import MagicMock

import openai
import pytest

from magentic_ui._ai_client import (
    _CONNECT_TIMEOUT_SECONDS,
    _READ_TIMEOUT_SECONDS,
    _build_timeout,
    humanize_model_error,
    is_retryable_model_error,
)


def _status_error(
    cls: type[openai.APIStatusError], status: int, *, code: str | None = None
) -> openai.APIStatusError:
    response = MagicMock()
    response.status_code = status
    response.request = MagicMock()
    err = cls(message="boom", response=response, body={"code": code})
    if code is not None:
        err.code = code
    return err


class TestBuildTimeout:
    def test_defaults(self):
        timeout = _build_timeout()
        assert timeout.connect == _CONNECT_TIMEOUT_SECONDS
        assert timeout.read == _READ_TIMEOUT_SECONDS
        # Pool acquisition uses the short connect timeout so an unreachable
        # server fails fast instead of waiting the full read timeout.
        assert timeout.pool == _CONNECT_TIMEOUT_SECONDS
        assert timeout.write == _READ_TIMEOUT_SECONDS


class TestHumanizeModelError:
    def test_connection_error_mentions_host(self):
        request = MagicMock()
        request.url.host = "model.local"
        err = openai.APIConnectionError(message="nope", request=request)
        msg = humanize_model_error(err)
        assert msg is not None
        assert "Could not reach the model server" in msg
        assert "model.local" in msg

    def test_timeout_error(self):
        err = openai.APITimeoutError(request=MagicMock())
        msg = humanize_model_error(err)
        assert msg is not None
        assert "did not respond in time" in msg

    def test_authentication_error(self):
        err = _status_error(openai.AuthenticationError, 401)
        assert "rejected the API key" in (humanize_model_error(err) or "")

    def test_quota_error(self):
        err = _status_error(openai.RateLimitError, 429, code="insufficient_quota")
        assert "out of quota" in (humanize_model_error(err) or "")

    def test_plain_rate_limit(self):
        err = _status_error(openai.RateLimitError, 429)
        assert "rate limiting" in (humanize_model_error(err) or "")

    def test_wrapped_cause_is_recognized(self):
        cause = openai.APIConnectionError(message="nope", request=MagicMock())
        wrapped = RuntimeError("Chat completion failed after 3 attempts")
        wrapped.__cause__ = cause
        msg = humanize_model_error(wrapped)
        assert msg is not None
        assert "Could not reach the model server" in msg

    def test_unrecognized_error_returns_none(self):
        assert humanize_model_error(ValueError("something else")) is None


class TestIsRetryableModelError:
    def test_timeout_is_retryable(self):
        assert is_retryable_model_error(openai.APITimeoutError(request=MagicMock()))

    def test_connection_error_is_fatal(self):
        err = openai.APIConnectionError(message="nope", request=MagicMock())
        assert not is_retryable_model_error(err)

    def test_server_error_is_retryable(self):
        assert is_retryable_model_error(_status_error(openai.InternalServerError, 503))

    def test_auth_error_is_fatal(self):
        assert not is_retryable_model_error(
            _status_error(openai.AuthenticationError, 401)
        )

    def test_not_found_is_fatal(self):
        assert not is_retryable_model_error(_status_error(openai.NotFoundError, 404))

    def test_plain_rate_limit_is_retryable(self):
        assert is_retryable_model_error(_status_error(openai.RateLimitError, 429))

    def test_quota_is_fatal(self):
        err = _status_error(openai.RateLimitError, 429, code="insufficient_quota")
        assert not is_retryable_model_error(err)

    def test_non_model_error_is_fatal(self):
        assert not is_retryable_model_error(ValueError("validation"))


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
