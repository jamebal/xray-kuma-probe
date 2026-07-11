from __future__ import annotations

from collections import Counter, defaultdict
from hashlib import sha256
from urllib.parse import parse_qsl, unquote, urlsplit

from .decoder import decode_subscription
from .models import ParseResult, ProxyNode


def _digest(value: str, length: int = 12) -> str:
    return sha256(value.encode()).hexdigest()[:length]


def _parse_line(line: str) -> ProxyNode:
    parsed = urlsplit(line)
    protocol = parsed.scheme.lower()
    if protocol not in {"vless", "trojan"}:
        raise ValueError("不支持的协议")
    if not parsed.hostname or not parsed.port or not parsed.username:
        raise ValueError("节点缺少服务器、端口或凭据")
    display_name = (
        unquote(parsed.fragment).strip() or f"{protocol.upper()}-{parsed.hostname}-{parsed.port}"
    )
    credential = unquote(parsed.username)
    params = {key: value for key, value in parse_qsl(parsed.query, keep_blank_values=True)}
    canonical = "|".join(
        (
            protocol,
            parsed.hostname.lower(),
            str(parsed.port),
            credential,
            repr(sorted(params.items())),
        )
    )
    fingerprint = _digest(canonical, 16)
    return ProxyNode(
        node_key=f"{protocol}:{display_name}",
        display_name=display_name,
        protocol=protocol,  # type: ignore[arg-type]
        server=parsed.hostname,
        port=parsed.port,
        credential=credential,
        fingerprint=fingerprint,
        params=params,
    )


def parse_subscription(content: str) -> ParseResult:
    decoded = decode_subscription(content)
    parsed_nodes: list[ProxyNode] = []
    ignored: Counter[str] = Counter()
    invalid_count = 0
    for raw_line in decoded.replace("\r\n", "\n").split("\n"):
        line = raw_line.strip().lstrip("\ufeff")
        if not line:
            continue
        scheme = line.partition("://")[0].lower() if "://" in line else ""
        if scheme not in {"vless", "trojan"}:
            if scheme:
                ignored[scheme] += 1
            else:
                invalid_count += 1
            continue
        try:
            parsed_nodes.append(_parse_line(line))
        except (ValueError, UnicodeError):
            invalid_count += 1

    grouped: dict[str, list[ProxyNode]] = defaultdict(list)
    for node in parsed_nodes:
        grouped[node.node_key].append(node)
    nodes: list[ProxyNode] = []
    seen_fingerprints: set[str] = set()
    for node in parsed_nodes:
        if node.fingerprint in seen_fingerprints:
            continue
        seen_fingerprints.add(node.fingerprint)
        key = node.node_key
        if len(grouped[key]) > 1:
            key = f"{key}:{_digest(node.server.lower() + ':' + str(node.port), 6)}"
        nodes.append(
            ProxyNode(
                key,
                node.display_name,
                node.protocol,
                node.server,
                node.port,
                node.credential,
                node.fingerprint,
                node.params,
            )
        )
    return ParseResult(nodes, dict(ignored), invalid_count)
