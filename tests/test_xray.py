from app.subscription.parser import parse_subscription
from app.xray.config_builder import build_config

from .test_subscription import TROJAN, VLESS


def test_builds_isolated_local_socks_routes() -> None:
    nodes = parse_subscription(f"{VLESS}\n{TROJAN}").nodes
    config = build_config([(nodes[0], 21001), (nodes[1], 21002)])
    assert [item["listen"] for item in config["inbounds"]] == ["127.0.0.1", "127.0.0.1"]
    assert [item["port"] for item in config["inbounds"]] == [21001, 21002]
    assert len({item["port"] for item in config["inbounds"]}) == 2
    routes = config["routing"]["rules"]
    for inbound, outbound, route in zip(
        config["inbounds"], config["outbounds"], routes, strict=True
    ):
        assert route["inboundTag"] == [inbound["tag"]]
        assert route["outboundTag"] == outbound["tag"]


def test_maps_reality_and_grpc_stream_settings() -> None:
    reality = "vless://id@example.com:443?encryption=none&flow=xtls-rprx-vision&security=reality&type=tcp&sni=x.example&fp=chrome&pbk=public&sid=abcd&spx=%2F#R"
    grpc = parse_subscription(TROJAN).nodes[0]
    config = build_config([(parse_subscription(reality).nodes[0], 21001), (grpc, 21002)])
    reality_stream = config["outbounds"][0]["streamSettings"]
    assert reality_stream["security"] == "reality"
    assert reality_stream["realitySettings"]["publicKey"] == "public"
    assert reality_stream["realitySettings"]["spiderX"] == "/"
    assert config["outbounds"][1]["streamSettings"]["grpcSettings"]["serviceName"] == "edge"


def test_maps_explicit_tls_allow_insecure_values() -> None:
    enabled = parse_subscription(
        "trojan://secret@example.com:443?security=tls&sni=edge.example&allowInsecure=1#Enabled"
    ).nodes[0]
    disabled = parse_subscription(
        "trojan://secret@example.com:443?security=tls&sni=edge.example&allowInsecure=false#Disabled"
    ).nodes[0]
    missing = parse_subscription(
        "trojan://secret@example.com:443?security=tls&sni=edge.example#Missing"
    ).nodes[0]

    config = build_config([(enabled, 21001), (disabled, 21002), (missing, 21003)])
    tls_settings = [outbound["streamSettings"]["tlsSettings"] for outbound in config["outbounds"]]

    assert tls_settings[0]["allowInsecure"] is True
    assert tls_settings[1]["allowInsecure"] is False
    assert "allowInsecure" not in tls_settings[2]


def test_uses_peer_only_as_tls_server_name_fallback() -> None:
    peer_only = parse_subscription(
        "trojan://secret@example.com:443?security=tls&peer=peer.example#Peer"
    ).nodes[0]
    explicit_sni = parse_subscription(
        "trojan://secret@example.com:443?security=tls&peer=peer.example&sni=sni.example#SNI"
    ).nodes[0]

    config = build_config([(peer_only, 21001), (explicit_sni, 21002)])
    tls_settings = [outbound["streamSettings"]["tlsSettings"] for outbound in config["outbounds"]]

    assert tls_settings[0]["serverName"] == "peer.example"
    assert tls_settings[1]["serverName"] == "sni.example"
