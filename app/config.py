from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    subscription_url: str
    kuma_url: str
    kuma_username: str
    kuma_password: str
    kuma_status_page_slug: str = ""
    monitor_name_prefix: str = "Proxy"
    kuma_monitor_group: str = "Proxy Nodes"
    probe_interval: int = Field(60, ge=10)
    kuma_heartbeat_interval: int = Field(75, ge=10)
    subscription_sync_interval: int = Field(300, ge=30)
    probe_timeout: float = Field(10, gt=0)
    probe_connect_timeout: float = Field(5, gt=0)
    probe_concurrency: int = Field(10, ge=1, le=100)
    failure_threshold: int = Field(2, ge=1)
    recovery_threshold: int = Field(1, ge=1)
    test_urls: Annotated[list[str], NoDecode] = ["https://cp.cloudflare.com/generate_204"]
    xray_binary: Path = Path("/usr/local/bin/xray")
    xray_config: Path = Path("/app/generated/xray.json")
    socks_port_start: int = 20000
    socks_port_end: int = 29999
    removed_node_policy: Literal["pause", "delete"] = "pause"
    removed_node_grace_period: int = Field(86400, ge=0)
    log_level: str = "INFO"
    tls_verify: bool = True
    database_path: Path = Path("/app/data/state.db")
    health_listen: str = "0.0.0.0"
    health_port: int = Field(8080, ge=1, le=65535)
    kuma_timeout: float = Field(10, gt=0)
    kuma_retries: int = Field(3, ge=1, le=10)

    @field_validator("test_urls", mode="before")
    @classmethod
    def split_urls(cls, value: object) -> object:
        return (
            [part.strip() for part in value.split(",") if part.strip()]
            if isinstance(value, str)
            else value
        )

    @model_validator(mode="after")
    def validate_ports(self) -> "Settings":
        if self.socks_port_start > self.socks_port_end:
            raise ValueError("SOCKS_PORT_START 不能大于 SOCKS_PORT_END")
        if self.kuma_heartbeat_interval <= self.probe_interval:
            raise ValueError("KUMA_HEARTBEAT_INTERVAL 必须大于 PROBE_INTERVAL")
        return self
