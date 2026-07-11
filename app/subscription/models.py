from dataclasses import dataclass, field
from typing import Literal

Protocol = Literal["vless", "trojan"]


@dataclass(frozen=True, slots=True)
class ProxyNode:
    node_key: str
    display_name: str
    protocol: Protocol
    server: str
    port: int
    credential: str
    fingerprint: str
    params: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ParseResult:
    nodes: list[ProxyNode]
    ignored_protocols: dict[str, int]
    invalid_count: int
