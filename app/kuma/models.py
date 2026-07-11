from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class KumaMonitor:
    id: int
    name: str
    push_token: str
    active: bool
    raw: dict[str, Any] = field(default_factory=dict, compare=False)


class KumaCompatibilityError(RuntimeError):
    """Kuma Internal API 与支持的协议不兼容。"""
