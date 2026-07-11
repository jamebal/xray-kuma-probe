import base64

from app.subscription.decoder import decode_subscription
from app.subscription.parser import parse_subscription

VLESS = "vless://11111111-1111-1111-1111-111111111111@example.com:443?security=tls&type=ws&host=cdn.example.com&path=%2Fws#%F0%9F%87%BA%F0%9F%87%B8%20LA"
TROJAN = "trojan://p%40ss@[2001:db8::1]:443?security=tls&type=grpc&serviceName=edge#Tokyo"


def test_decodes_plain_and_unpadded_base64_crlf() -> None:
    plain = f"\ufeff{VLESS}\r\ninvalid://ignored\r\n{TROJAN}\r\n"
    encoded = base64.b64encode(plain.encode()).decode().rstrip("=")
    assert decode_subscription(encoded) == plain.lstrip("\ufeff")
    assert decode_subscription(plain) == plain.lstrip("\ufeff")


def test_parses_unicode_ipv6_and_counts_ignored_lines() -> None:
    result = parse_subscription(f"{VLESS}\nss://secret\ninvalid\n{TROJAN}")
    assert [node.display_name for node in result.nodes] == ["🇺🇸 LA", "Tokyo"]
    assert result.nodes[1].server == "2001:db8::1"
    assert result.nodes[1].credential == "p@ss"
    assert result.ignored_protocols == {"ss": 1}
    assert result.invalid_count == 1


def test_duplicate_names_have_stable_distinct_keys_when_reordered() -> None:
    second = VLESS.replace("example.com", "other.example.com")
    first_result = parse_subscription(f"{VLESS}\n{second}").nodes
    second_result = parse_subscription(f"{second}\n{VLESS}").nodes
    assert {node.node_key for node in first_result} == {node.node_key for node in second_result}
    assert len({node.node_key for node in first_result}) == 2


def test_credential_change_preserves_unique_logical_identity() -> None:
    changed = VLESS.replace(
        "11111111-1111-1111-1111-111111111111", "22222222-2222-2222-2222-222222222222"
    )
    assert (
        parse_subscription(VLESS).nodes[0].node_key == parse_subscription(changed).nodes[0].node_key
    )
