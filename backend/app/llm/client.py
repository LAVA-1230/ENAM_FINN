"""Provider-agnostic LLM client.

complete(prompt_name, tier, inputs, schema=None) -> dict | str
- Prompts live in llm/prompts/<name>.md with a `version:` header, a `---system` and a `---user` part.
  Placeholders are {{name}} so JSON braces in prompts need no escaping.
- Every call checks the cache first (prompt + version + model + inputs), and logs tokens and cost.
- JSON mode where the provider supports it; otherwise parse, validate with Pydantic, retry once
  with the validation error appended.
- If no provider is configured, raises LlmUnavailable and callers fall back to rules/templates."""
import json
import logging
import re
import time
from functools import lru_cache
from pathlib import Path

import httpx
from pydantic import BaseModel, ValidationError

from ..config import DEFAULT_MODELS, get_settings
from . import cache, usage

log = logging.getLogger(__name__)
PROMPTS = Path(__file__).parent / "prompts"
TIMEOUT = {"fast": 45, "smart": 90}


class LlmUnavailable(Exception):
    pass


@lru_cache
def load_prompt(name: str) -> dict:
    raw = (PROMPTS / f"{name}.md").read_text(encoding="utf-8")
    version = re.search(r"^version:\s*(\S+)", raw, re.M).group(1)
    system = raw.split("---system", 1)[1].split("---user", 1)[0].strip()
    user = raw.split("---user", 1)[1].strip()
    return {"version": version, "system": system, "user": user}


def render(template: str, inputs: dict) -> str:
    def sub(m):
        v = inputs.get(m.group(1), "")
        return v if isinstance(v, str) else json.dumps(v, ensure_ascii=False, default=str)
    return re.sub(r"\{\{(\w+)\}\}", sub, template)


def model_for(tier: str) -> str:
    s = get_settings()
    fast, smart = DEFAULT_MODELS.get(s.llm_provider, ("", ""))
    return (s.llm_fast_model or fast) if tier == "fast" else (s.llm_smart_model or smart)


def available() -> bool:
    return get_settings().llm_enabled


def complete(prompt_name: str, tier: str, inputs: dict, schema: type[BaseModel] | None = None,
             job: str | None = None, use_cache: bool = True):
    s = get_settings()
    if not s.llm_enabled:
        raise LlmUnavailable("no LLM provider configured")
    p = load_prompt(prompt_name)
    model = model_for(tier)
    key = cache.make_key(prompt_name, p["version"], model, inputs)
    if use_cache:
        hit = cache.get(key)
        if hit is not None:
            usage.log(job, prompt_name, model, 0, 0, cached=True)
            return hit
    if usage.over_budget():
        raise LlmUnavailable("daily LLM budget reached")

    system = p["system"]
    if schema is not None:
        system += ("\n\nReturn only JSON matching this JSON schema:\n"
                   + json.dumps(schema.model_json_schema(), separators=(",", ":")))
    user = render(p["user"], inputs)

    out, err = None, None
    for attempt in range(2):
        msg = user if err is None else f"{user}\n\nYour previous reply was invalid: {err}. Return valid JSON only."
        text, tin, tout = _call(s.llm_provider, model, system, msg, json_mode=schema is not None, tier=tier)
        usage.log(job, prompt_name, model, tin, tout)
        if schema is None:
            out = text.strip()
            break
        try:
            data = _parse_json(text)
            out = schema.model_validate(data).model_dump()
            break
        except (ValueError, ValidationError) as e:
            err = str(e)[:400]
            log.info("%s invalid JSON (attempt %s): %s", prompt_name, attempt + 1, err)
    if out is None:
        raise ValueError(f"{prompt_name}: model did not return valid JSON")
    cache.put(key, out, model)
    return out


def _parse_json(text: str):
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"[\[{].*[\]}]", text, re.S)
        if not m:
            raise ValueError("no JSON found")
        return json.loads(m.group(0))


def _call(provider: str, model: str, system: str, user: str, json_mode: bool, tier: str) -> tuple[str, int, int]:
    key = get_settings().llm_api_key
    timeout = TIMEOUT[tier]
    for attempt in range(3):
        try:
            if provider == "gemini":
                return _gemini(key, model, system, user, json_mode, timeout)
            if provider in ("groq", "openai"):
                base = "https://api.groq.com/openai/v1" if provider == "groq" else "https://api.openai.com/v1"
                return _openai_like(base, key, model, system, user, json_mode, timeout)
            if provider == "anthropic":
                return _anthropic(key, model, system, user, timeout)
            raise LlmUnavailable(f"unknown provider {provider}")
        except httpx.HTTPStatusError as e:
            code = e.response.status_code
            if code in (429, 500, 502, 503, 504) and attempt < 2:
                time.sleep(4 * (attempt + 1))
                continue
            raise LlmUnavailable(f"{provider} {code}: {e.response.text[:200]}") from e
        except httpx.TransportError as e:
            if attempt < 2:
                time.sleep(2)
                continue
            raise LlmUnavailable(str(e)) from e
    raise LlmUnavailable("retries exhausted")


def _gemini(key, model, system, user, json_mode, timeout):
    body = {"systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {"temperature": 0.1}}
    if json_mode:
        body["generationConfig"]["responseMimeType"] = "application/json"
    r = httpx.post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                   params={"key": key}, json=body, timeout=timeout)
    r.raise_for_status()
    d = r.json()
    parts = (d.get("candidates") or [{}])[0].get("content", {}).get("parts", [])
    text = "".join(p.get("text", "") for p in parts)
    u = d.get("usageMetadata", {})
    return text, u.get("promptTokenCount", 0), u.get("candidatesTokenCount", 0)


def _openai_like(base, key, model, system, user, json_mode, timeout):
    body = {"model": model, "temperature": 0.1,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    r = httpx.post(f"{base}/chat/completions", headers={"Authorization": f"Bearer {key}"}, json=body, timeout=timeout)
    r.raise_for_status()
    d = r.json()
    u = d.get("usage", {})
    return d["choices"][0]["message"]["content"], u.get("prompt_tokens", 0), u.get("completion_tokens", 0)


def _anthropic(key, model, system, user, timeout):
    body = {"model": model, "max_tokens": 4096, "system": system,
            "messages": [{"role": "user", "content": user}]}
    r = httpx.post("https://api.anthropic.com/v1/messages",
                   headers={"x-api-key": key, "anthropic-version": "2023-06-01"}, json=body, timeout=timeout)
    r.raise_for_status()
    d = r.json()
    text = "".join(b.get("text", "") for b in d.get("content", []) if b.get("type") == "text")
    u = d.get("usage", {})
    return text, u.get("input_tokens", 0), u.get("output_tokens", 0)
