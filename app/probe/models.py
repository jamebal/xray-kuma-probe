from dataclasses import dataclass
from datetime import datetime
from typing import Literal

ErrorCategory = Literal[
    "TIMEOUT",
    "CONNECT_FAILED",
    "SOCKS_FAILED",
    "TLS_FAILED",
    "PROXY_FAILED",
    "DNS_FAILED",
    "HTTP_ERROR",
    "XRAY_UNAVAILABLE",
    "UNKNOWN",
]


@dataclass(frozen=True, slots=True)
class ProbeResult:
    success: bool
    total_time_ms: int | None
    status_code: int | None
    error_category: ErrorCategory | None
    checked_at: datetime

    @property
    def message(self) -> str:
        if self.success:
            return f"HTTP {self.status_code}" if self.status_code else "OK"
        return self.error_category or "UNKNOWN"
