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
