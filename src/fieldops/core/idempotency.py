"""Idempotency utilities: canonical request hashing and key validation."""

import hashlib
import json
from typing import Any
from pydantic import BaseModel


def compute_request_hash(payload: dict[str, Any] | BaseModel | str) -> str:
    """Compute a deterministic SHA-256 hash of canonical JSON request payload.

    Keys are recursively sorted and formatted with standard delimiters
    to guarantee identical hashes regardless of dictionary key ordering.
    """
    if isinstance(payload, BaseModel):
        data = payload.model_dump(mode="json")
    elif isinstance(payload, dict):
        data = payload
    elif isinstance(payload, str):
        try:
            data = json.loads(payload)
        except Exception:
            data = {"_raw": payload}
    else:
        data = {"_raw": str(payload)}

    canonical_json = json.dumps(
        data,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
