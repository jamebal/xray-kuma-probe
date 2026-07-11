import re

PATTERNS = (
    re.compile(r"(?i)(vless|trojan)://[^\s]+"),
    re.compile(r"(?i)(password|token|uuid|publicKey|pbk)([\"'=:\s]+)[^\s,}\"]+"),
    re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I),
)


def redact(value: str) -> str:
    result = value
    for pattern in PATTERNS:
        result = pattern.sub(
            lambda match: (
                f"{match.group(1)}://[REDACTED]"
                if match.lastindex and match.group(1).lower() in {"vless", "trojan"}
                else "[REDACTED]"
            ),
            result,
        )
    return result
