"""Small LLM provider helpers for OpenAI-compatible Perplexity calls."""

from __future__ import annotations

import os
from typing import Any, Mapping

import requests

PERPLEXITY_API_KEY_ENV = "PERPLEXITY_API_KEY"
PERPLEXITY_BASE_URL = "https://api.perplexity.ai"
PERPLEXITY_CHAT_COMPLETIONS_PATH = "/chat/completions"
DEFAULT_TIMEOUT_SECONDS = 30


class MissingProviderCredential(RuntimeError):
    """Raised when a provider credential is missing before any network call."""


def require_perplexity_api_key(env: Mapping[str, str] | None = None) -> str:
    """Return the Perplexity API key or fail clearly before a request is made."""
    source = os.environ if env is None else env
    api_key = source.get(PERPLEXITY_API_KEY_ENV)
    if not api_key:
        raise MissingProviderCredential(
            f"{PERPLEXITY_API_KEY_ENV} not set; create a Perplexity API key "
            f"and export it as {PERPLEXITY_API_KEY_ENV} before running LLM steps."
        )
    return api_key


def extract_assistant_text(response_payload: Mapping[str, Any]) -> str:
    """Extract choices[0].message.content from an OpenAI-compatible response."""
    try:
        text = response_payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError("provider response missing assistant message content") from exc
    if not isinstance(text, str) or not text:
        raise ValueError("provider response missing assistant message content")
    return text


def perplexity_chat_completion(
    *,
    messages: list[dict[str, Any]],
    model: str,
    env: Mapping[str, str] | None = None,
    session: Any = requests,
    base_url: str = PERPLEXITY_BASE_URL,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    temperature: float | None = None,
    max_tokens: int | None = None,
    response_format: dict[str, Any] | None = None,
) -> str:
    """Call Perplexity's OpenAI-compatible chat completions endpoint."""
    api_key = require_perplexity_api_key(env)
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
    }
    if temperature is not None:
        payload["temperature"] = temperature
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens
    if response_format is not None:
        payload["response_format"] = response_format

    response = session.post(
        base_url.rstrip("/") + PERPLEXITY_CHAT_COMPLETIONS_PATH,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=timeout,
    )
    response.raise_for_status()
    return extract_assistant_text(response.json())
