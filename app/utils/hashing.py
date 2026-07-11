import hashlib
import json
from typing import Any


def stable_hash(value: str | dict[str, Any]) -> str:
    payload = (
        value
        if isinstance(value, str)
        else json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    )
    return hashlib.sha256(payload.encode()).hexdigest()
