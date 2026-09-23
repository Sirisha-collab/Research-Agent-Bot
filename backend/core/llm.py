from __future__ import annotations

import json
import logging
import re
import time
from functools import lru_cache
from typing import Any

from backend.config import (
    LLM_API_KEY,
    LLM_RETRIES,
    LLM_BASE_URL,
    LLM_FAST_MODEL,
    LLM_MAX_TOKENS,
    LLM_MODEL,
    LLM_PROVIDER,
    LLM_TEMPERATURE,
    LLM_TIMEOUT,
)

log = logging.getLogger(__name__)


class LLMError(RuntimeError):
    pass


class FatalLLMError(LLMError):
    """Configuration-level failure: bad model name, bad key, no credit."""

NON_RETRYABLE = {400, 401, 402, 403, 404, 422}

FATAL_HINTS = (
    "does not exist or you do not have access",
    "model_not_found",
    "model_decommissioned",
    "insufficient balance",
    "invalid api key",
    "incorrect api key",
)


def _status_of(exc: Exception) -> int | None:
    status = getattr(exc, "status_code", None) or getattr(exc, "status", None)
    if isinstance(status, int):
        return status
    resp = getattr(exc, "response", None)
    code = getattr(resp, "status_code", None)
    return code if isinstance(code, int) else None


def _is_fatal(exc: Exception) -> bool:
    if _status_of(exc) in NON_RETRYABLE:
        return True
    text = str(exc).lower()
    return any(hint in text for hint in FATAL_HINTS)


def _explain(exc: Exception) -> str:
    status = _status_of(exc)
    text = str(exc)
    if status == 404 or "model_not_found" in text or "does not exist" in text:
        return (
            f"Model '{LLM_MODEL}' is not available on {LLM_PROVIDER}. "
            "Providers retire models regularly. Check the current list at "
            f"{LLM_BASE_URL}/models and set LLM_MODEL / LLM_FAST_MODEL in .env."
        )
    if status == 401:
        return f"{LLM_PROVIDER} rejected the API key. Check it in .env."
    if status == 402 or "insufficient balance" in text.lower():
        return f"The {LLM_PROVIDER} account has no credit remaining."
    if status in (400, 422):
        return f"{LLM_PROVIDER} rejected the request: {text}"
    return text


@lru_cache(maxsize=1)
def _client():
    from openai import OpenAI

    if not LLM_API_KEY:
        raise LLMError(
            f"No API key found for provider '{LLM_PROVIDER}'. "
            "Put GROQ_API_KEY=... (or DEEPSEEK_API_KEY=...) in your .env file."
        )
    return OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL, timeout=LLM_TIMEOUT)


def chat(
    prompt: str,
    system: str = "You are a careful research assistant.",
    *,
    fast: bool = False,
    temperature: float | None = None,
    max_tokens: int | None = None,
    json_mode: bool = False,
    retries: int | None = None,
) -> str:
    retries = LLM_RETRIES if retries is None else retries
    messages = [{"role": "system", "content": system}, {"role": "user", "content": prompt}]
    kwargs: dict[str, Any] = {
        "model": LLM_FAST_MODEL if fast else LLM_MODEL,
        "messages": messages,
        "temperature": LLM_TEMPERATURE if temperature is None else temperature,
        "max_tokens": max_tokens or LLM_MAX_TOKENS,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    last: Exception | None = None
    for attempt in range(retries):
        try:
            resp = _client().chat.completions.create(**kwargs)
            return (resp.choices[0].message.content or "").strip()
        except FatalLLMError:
            raise
        except Exception as exc:
            if _is_fatal(exc):
                # No amount of retrying fixes a bad model name, key or balance.
                raise FatalLLMError(_explain(exc)) from exc
            last = exc
            if attempt == retries - 1:
                break
            wait = 2 ** attempt * 2
            log.warning("LLM call failed (%s). Retry %d/%d in %ss",
                        exc, attempt + 1, retries - 1, wait)
            time.sleep(wait)
    raise LLMError(f"LLM request failed after {retries} attempts: {last}")


def chat_json(prompt: str, system: str, *, fast: bool = False,
              fallback: Any = None, max_tokens: int | None = None) -> Any:

    system = system + "\nRespond with a single valid JSON object and nothing else."
    try:
        raw = chat(prompt, system, fast=fast, json_mode=True, max_tokens=max_tokens,
                   temperature=0.0)
    except FatalLLMError:
        raise
    except LLMError:
        if fallback is not None:
            return fallback
        raise
    cleaned = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.M).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        m = re.search(r"[\{\[].*[\}\]]", cleaned, re.S)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
    log.warning("Could not parse JSON from model output")
    return fallback
