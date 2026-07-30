from __future__ import annotations

import json
import logging
import re
import time
from functools import lru_cache
from typing import Any

from backend.config import (
    LLM_API_KEY,
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
    retries: int = 3,
) -> str:
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
        except LLMError:
            raise
        except Exception as exc:
            status = getattr(exc, "status_code", None)
            if status in (400, 401, 402, 403, 422):
                raise LLMError(
                    f"{LLM_PROVIDER} rejected the request ({status}). "
                    "402 = empty balance, 401 = bad key, 400/422 = bad request. "
                    "Retrying will not help."
                ) from exc
            last = exc
            wait = 2 ** attempt * 2
            log.warning("LLM call failed (%s). Retrying in %ss", exc, wait)
            time.sleep(wait)
    raise LLMError(f"LLM request failed after {retries} attempts: {last}")


def chat_json(prompt: str, system: str, *, fast: bool = False,
              fallback: Any = None, max_tokens: int | None = None) -> Any:
    """Ask for JSON and parse defensively - models still wrap it in fences."""
    system = system + "\nRespond with a single valid JSON object and nothing else."
    try:
        raw = chat(prompt, system, fast=fast, json_mode=True, max_tokens=max_tokens,
                   temperature=0.0)
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
