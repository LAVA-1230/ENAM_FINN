"""LLM output cache keyed by prompt name + prompt version + model + canonical inputs."""
import hashlib
import json

from ..db import session_scope
from ..models import LlmCache


def make_key(prompt_name: str, version: str, model: str, inputs: dict) -> str:
    canon = json.dumps(inputs, sort_keys=True, ensure_ascii=False, default=str)
    h = hashlib.sha256(f"{model}\n{canon}".encode()).hexdigest()[:40]
    return f"{prompt_name}:{version}:{h}"


def get(key: str):
    with session_scope() as db:
        row = db.get(LlmCache, key)
        return row.output if row else None


def put(key: str, output, model: str):
    with session_scope() as db:
        row = db.get(LlmCache, key)
        if row:
            row.output = output
        else:
            db.add(LlmCache(key=key, output=output, model=model))
