"""Provider-agnostic LLM client.

Supports: groq | openai (OpenAI-compatible) | ollama (local).
All routed through a single chat() call returning text.
"""
from __future__ import annotations
import json
import os

import requests

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
OPENAI_DEFAULT_URL = "https://api.openai.com/v1/chat/completions"


class LLMError(RuntimeError):
    pass


def _post(url: str, headers: dict, payload: dict, timeout: int) -> dict:
    import time
    for attempt in range(4):
        resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
        if resp.status_code == 429:
            # honor retry hint if present, else backoff
            wait = 5 * (attempt + 1)
            try:
                msg = resp.json()["error"]["message"]
                import re
                m = re.search(r"try again in ([\d.]+)s", msg)
                if m:
                    wait = float(m[1]) + 1
            except Exception:
                pass
            if attempt < 3:
                time.sleep(min(wait, 30))
                continue
        if resp.status_code >= 400:
            raise LLMError(f"{resp.status_code}: {resp.text[:400]}")
        return resp.json()
    raise LLMError("429: rate limit — retries exhausted")


def chat(
    messages: list[dict],
    provider: str = "groq",
    model: str = "llama-3.3-70b-versatile",
    temperature: float = 0.7,
    json_mode: bool = False,
    timeout: int = 90,
) -> str:
    """Send chat messages, return assistant text. Raises LLMError on failure."""
    provider = provider.lower()

    if provider == "groq":
        key = os.getenv("GROQ_API_KEY")
        if not key:
            raise LLMError("GROQ_API_KEY not set. Add it to .env (console.groq.com).")
        payload = {"model": model, "messages": messages, "temperature": temperature,
                   "max_completion_tokens": 3000}
        # gpt-oss reasoning models: keep reasoning short so content isn't starved
        if "gpt-oss" in model:
            payload["reasoning_effort"] = "low"
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        data = _post(GROQ_URL, {"Authorization": f"Bearer {key}"}, payload, timeout)
        return data["choices"][0]["message"]["content"]

    if provider == "openai":
        key = os.getenv("OPENAI_API_KEY")
        if not key:
            raise LLMError("OPENAI_API_KEY not set.")
        url = os.getenv("OPENAI_BASE_URL") or OPENAI_DEFAULT_URL
        if not url.endswith("/chat/completions"):
            url = url.rstrip("/") + "/chat/completions"
        payload = {"model": model, "messages": messages, "temperature": temperature}
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        data = _post(url, {"Authorization": f"Bearer {key}"}, payload, timeout)
        return data["choices"][0]["message"]["content"]

    if provider == "ollama":
        host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        payload = {"model": model, "messages": messages, "stream": False,
                   "options": {"temperature": temperature}}
        if json_mode:
            payload["format"] = "json"
        data = _post(host.rstrip("/") + "/api/chat", {}, payload, timeout)
        return data["message"]["content"]

    raise LLMError(f"unknown provider: {provider}")


def chat_json(messages: list[dict], **kw) -> dict:
    """chat() expecting JSON output; tolerant parse with fallback.

    Some reasoning models (gpt-oss) fail strict json_object mode. On failure,
    retry without json_mode and extract the JSON object manually.
    """
    try:
        raw = chat(messages, json_mode=True, **kw)
    except LLMError:
        raw = chat(messages, json_mode=False, **kw)
    raw = (raw or "").strip()
    if not raw:
        raw = chat(messages, json_mode=False, **kw).strip()
    # strip code fences if model wrapped output
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        if raw.startswith("json"):
            raw = raw[4:]
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start, end = raw.find("{"), raw.rfind("}")
        if start != -1 and end != -1:
            return json.loads(raw[start:end + 1])
        raise
