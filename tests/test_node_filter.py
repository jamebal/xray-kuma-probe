from app.subscription.filter import partition_nodes
from app.subscription.parser import parse_subscription

from .test_subscription import TROJAN, VLESS


def test_partition_nodes_matches_display_name_by_casefolded_substring() -> None:
    nodes = parse_subscription(f"{VLESS}\n{TROJAN}").nodes

    included, excluded = partition_nodes(nodes, ["la", "不存在"])

    assert [node.display_name for node in included] == ["Tokyo"]
    assert [node.display_name for node in excluded] == ["🇺🇸 LA"]


def test_partition_nodes_without_keywords_keeps_all_nodes() -> None:
    nodes = parse_subscription(f"{VLESS}\n{TROJAN}").nodes

    included, excluded = partition_nodes(nodes, [])

    assert included == nodes
    assert excluded == []
