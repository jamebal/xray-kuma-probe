from typing import Any

from app.subscription.models import ProxyNode


def _stream_settings(node: ProxyNode) -> dict[str, Any]:
    p = node.params
    network = p.get("type", "tcp").lower()
    if network == "splithttp":
        network = "xhttp"
    stream: dict[str, Any] = {
        "network": network,
        "security": p.get("security", "tls" if node.protocol == "trojan" else "none"),
    }
    if stream["security"] == "tls":
        tls: dict[str, Any] = {
            "serverName": p.get("sni", p.get("host", "")),
            "fingerprint": p.get("fp", "chrome"),
        }
        if p.get("alpn"):
            tls["alpn"] = [item.strip() for item in p["alpn"].split(",")]
        stream["tlsSettings"] = tls
    elif stream["security"] == "reality":
        stream["realitySettings"] = {
            "serverName": p.get("sni", ""),
            "fingerprint": p.get("fp", "chrome"),
            "publicKey": p.get("pbk", ""),
            "shortId": p.get("sid", ""),
            "spiderX": p.get("spx", ""),
        }
    if network == "ws":
        stream["wsSettings"] = {"path": p.get("path", "/"), "headers": {"Host": p.get("host", "")}}
    elif network == "grpc":
        stream["grpcSettings"] = {
            "serviceName": p.get("serviceName", ""),
            "multiMode": p.get("mode") == "multi",
        }
    elif network == "httpupgrade":
        stream["httpupgradeSettings"] = {"path": p.get("path", "/"), "host": p.get("host", "")}
    elif network == "xhttp":
        stream["xhttpSettings"] = {
            "path": p.get("path", "/"),
            "host": p.get("host", ""),
            "mode": p.get("mode", "auto"),
        }
    return stream


def _outbound(node: ProxyNode, tag: str) -> dict[str, Any]:
    server: dict[str, Any] = {"address": node.server, "port": node.port}
    if node.protocol == "vless":
        server["users"] = [
            {
                "id": node.credential,
                "encryption": node.params.get("encryption", "none"),
                "flow": node.params.get("flow", ""),
            }
        ]
    else:
        server["password"] = node.credential
    return {
        "tag": tag,
        "protocol": node.protocol,
        "settings": {"vnext" if node.protocol == "vless" else "servers": [server]},
        "streamSettings": _stream_settings(node),
    }


def build_config(nodes: list[tuple[ProxyNode, int]]) -> dict[str, Any]:
    inbounds: list[dict[str, Any]] = []
    outbounds: list[dict[str, Any]] = []
    rules: list[dict[str, Any]] = []
    for index, (node, port) in enumerate(nodes):
        suffix = f"{index}-{node.fingerprint[:8]}"
        inbound_tag, outbound_tag = f"in-{suffix}", f"out-{suffix}"
        inbounds.append(
            {
                "tag": inbound_tag,
                "listen": "127.0.0.1",
                "port": port,
                "protocol": "socks",
                "settings": {"auth": "noauth", "udp": False},
            }
        )
        outbounds.append(_outbound(node, outbound_tag))
        rules.append({"type": "field", "inboundTag": [inbound_tag], "outboundTag": outbound_tag})
    return {
        "log": {"loglevel": "warning"},
        "inbounds": inbounds,
        "outbounds": outbounds,
        "routing": {"domainStrategy": "AsIs", "rules": rules},
    }
