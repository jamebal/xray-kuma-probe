from .models import ProxyNode


def partition_nodes(
    nodes: list[ProxyNode], keywords: list[str]
) -> tuple[list[ProxyNode], list[ProxyNode]]:
    folded_keywords = [keyword.casefold() for keyword in keywords]
    included: list[ProxyNode] = []
    excluded: list[ProxyNode] = []
    for node in nodes:
        target = node.display_name.casefold()
        destination = (
            excluded if any(keyword in target for keyword in folded_keywords) else included
        )
        destination.append(node)
    return included, excluded
