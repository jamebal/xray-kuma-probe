# 节点过滤与多 URL 平均延迟实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**目标：** 增加按节点显示名称关键字立即排除监控的能力，并让所有 `TEST_URLS` 均成功后上报各 URL 请求延迟的平均值。

**架构：** 配置层负责把两个逗号分隔环境变量解析为非空字符串列表；订阅过滤由独立纯函数完成，应用同步层只持久化保留节点，并通过仓储接口立即停用既有排除节点。探测层顺序请求全部 URL、逐次计时，失败时不返回部分平均值，全部成功时返回算术平均值。

**技术栈：** Python 3.12、Pydantic Settings、asyncio、httpx、SQLite、pytest、pytest-asyncio、Ruff、mypy

---

### 任务 1：补全列表配置解析与校验

**文件：**

- 修改：`app/config.py`
- 修改：`tests/test_config.py`

- [ ] **步骤 1：编写失败测试**

在 `tests/test_config.py` 增加公共必填环境变量 fixture，并增加以下测试：

```python
@pytest.fixture(autouse=True)
def required_settings(monkeypatch) -> None:
    monkeypatch.setenv("SUBSCRIPTION_URL", "https://example.test/sub")
    monkeypatch.setenv("KUMA_URL", "http://kuma.test:3001")
    monkeypatch.setenv("KUMA_USERNAME", "user")
    monkeypatch.setenv("KUMA_PASSWORD", "password")


def test_node_exclude_keywords_accept_comma_separated_value(monkeypatch) -> None:
    monkeypatch.setenv("NODE_EXCLUDE_KEYWORDS", " Expire, 官网, ,剩余流量 ")

    settings = Settings(_env_file=None)

    assert settings.node_exclude_keywords == ["Expire", "官网", "剩余流量"]


def test_node_exclude_keywords_default_to_empty_list(monkeypatch) -> None:
    assert Settings(_env_file=None).node_exclude_keywords == []


def test_test_urls_rejects_empty_environment_value(monkeypatch) -> None:
    monkeypatch.setenv("TEST_URLS", " , ")

    with pytest.raises(ValidationError, match="TEST_URLS"):
        Settings(_env_file=None)
```

fixture 使用 `autouse=True` 设置 `SUBSCRIPTION_URL`、`KUMA_URL`、`KUMA_USERNAME`
和 `KUMA_PASSWORD`，删除各测试中的重复设置。

- [ ] **步骤 2：运行测试并确认按预期失败**

运行：

```bash
.venv/bin/pytest tests/test_config.py -q
```

预期：关键字属性不存在，且空 `TEST_URLS` 未被拒绝。

- [ ] **步骤 3：编写最小实现**

在 `Settings` 中增加：

```python
node_exclude_keywords: Annotated[list[str], NoDecode] = Field(default_factory=list)
```

将列表拆分 validator 扩展到两个字段，并增加非空 URL 校验：

```python
@field_validator("test_urls", "node_exclude_keywords", mode="before")
@classmethod
def split_comma_separated(cls, value: object) -> object:
    return (
        [part.strip() for part in value.split(",") if part.strip()]
        if isinstance(value, str)
        else value
    )

@field_validator("test_urls")
@classmethod
def require_test_urls(cls, value: list[str]) -> list[str]:
    if not value:
        raise ValueError("TEST_URLS 至少需要一个 URL")
    return value
```

- [ ] **步骤 4：运行配置测试并确认通过**

运行：

```bash
.venv/bin/pytest tests/test_config.py -q
```

预期：全部通过。

- [ ] **步骤 5：提交配置改动**

```bash
git add app/config.py tests/test_config.py
git commit -m "feat: 增加节点过滤关键字配置"
```

### 任务 2：实现节点名称分组过滤

**文件：**

- 创建：`app/subscription/filter.py`
- 创建：`tests/test_node_filter.py`

- [ ] **步骤 1：编写失败测试**

创建 `tests/test_node_filter.py`：

```python
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
```

- [ ] **步骤 2：运行测试并确认按预期失败**

运行：

```bash
.venv/bin/pytest tests/test_node_filter.py -q
```

预期：因 `app.subscription.filter` 不存在而失败。

- [ ] **步骤 3：编写最小实现**

创建 `app/subscription/filter.py`：

```python
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
            excluded
            if any(keyword in target for keyword in folded_keywords)
            else included
        )
        destination.append(node)
    return included, excluded
```

- [ ] **步骤 4：运行过滤测试并确认通过**

运行：

```bash
.venv/bin/pytest tests/test_node_filter.py -q
```

预期：2 个测试通过。

- [ ] **步骤 5：提交过滤纯函数**

```bash
git add app/subscription/filter.py tests/test_node_filter.py
git commit -m "feat: 按名称关键字分组订阅节点"
```

### 任务 3：增加既有过滤节点立即停用接口

**文件：**

- 修改：`app/state/repository.py`
- 修改：`tests/test_state.py`

- [ ] **步骤 1：编写失败测试**

在 `tests/test_state.py` 增加：

```python
@pytest.mark.asyncio
async def test_disable_nodes_is_immediate_and_does_not_disable_other_nodes(tmp_path: Path) -> None:
    db = Database(tmp_path / "state.db")
    await db.initialize()
    repo = NodeRepository(db, 20000, 20010)
    first, second = parse_subscription(f"{VLESS}\n{TROJAN}").nodes
    await repo.upsert_node(first)
    await repo.upsert_node(second)

    await repo.disable_nodes({first.node_key})

    records = {record.node_key: record for record in await repo.list_nodes()}
    assert records[first.node_key].enabled is False
    assert records[first.node_key].removed_at is not None
    assert records[second.node_key].enabled is True
    await db.close()
```

并从 `tests.test_subscription` 导入 `TROJAN`。

- [ ] **步骤 2：运行测试并确认按预期失败**

运行：

```bash
.venv/bin/pytest tests/test_state.py::test_disable_nodes_is_immediate_and_does_not_disable_other_nodes -q
```

预期：`NodeRepository` 没有 `disable_nodes`。

- [ ] **步骤 3：编写最小实现**

在 `NodeRepository` 中增加：

```python
async def disable_nodes(self, node_keys: set[str]) -> None:
    if not node_keys:
        return
    conn, now = self.db.require(), time.time()
    keys = sorted(node_keys)
    placeholders = ",".join("?" for _ in keys)
    conn.execute(
        f"UPDATE nodes SET removed_at=?,enabled=0 "
        f"WHERE node_key IN ({placeholders}) AND enabled=1",
        (now, *keys),
    )
    conn.commit()
```

集合在绑定前转换为稳定序列，避免参数顺序依赖；动态内容仅为按集合长度生成的
`?` 占位符，不拼接用户输入。

- [ ] **步骤 4：运行仓储测试并确认通过**

运行：

```bash
.venv/bin/pytest tests/test_state.py -q
```

预期：全部通过。

- [ ] **步骤 5：提交仓储改动**

```bash
git add app/state/repository.py tests/test_state.py
git commit -m "feat: 支持立即停用过滤节点"
```

### 任务 4：把过滤接入订阅同步和监控流程

**文件：**

- 修改：`app/main.py`
- 创建：`tests/test_application.py`

- [ ] **步骤 1：编写失败的同步行为测试**

创建 `tests/test_application.py`。使用 `object.__new__(Application)` 注入以下
最小 fake 依赖，避免启动网络连接：

```python
from types import SimpleNamespace

import pytest

from app.main import Application

from .test_subscription import TROJAN, VLESS


class FakeFetcher:
    async def fetch(self, url: str) -> str:
        return f"{VLESS}\n{TROJAN}"


class FakeRepository:
    def __init__(self) -> None:
        self.upserted_names: list[str] = []
        self.disabled_keys: set[str] = set()
        self.active_keys: set[str] = set()

    async def upsert_node(self, node):
        self.upserted_names.append(node.display_name)
        return SimpleNamespace(socks_port=20000)

    async def disable_nodes(self, node_keys: set[str]) -> None:
        self.disabled_keys = node_keys

    async def mark_missing(self, active_keys: set[str], grace_period: int) -> None:
        self.active_keys = active_keys

    async def list_nodes(self):
        return []


class FakeStatusPage:
    async def sync(self, active_ids: set[int], owned_ids: set[int]) -> None:
        return None


class FakeXray:
    def __init__(self) -> None:
        self.installed_config = None
        self.restarted = False

    async def install_config(self, config) -> bool:
        self.installed_config = config
        return True

    async def restart(self) -> None:
        self.restarted = True


class FakeReconciler:
    def __init__(self, *args) -> None:
        pass

    async def reconcile(self, records) -> None:
        return None


@pytest.mark.asyncio
async def test_sync_subscription_excludes_matching_nodes_and_disables_existing(
    monkeypatch,
) -> None:
    monkeypatch.setattr("app.main.KumaReconciler", FakeReconciler)
    app = object.__new__(Application)
    app.settings = SimpleNamespace(
        subscription_url="https://example.test/sub",
        node_exclude_keywords=["la"],
        removed_node_grace_period=86400,
        monitor_name_prefix="Proxy",
        kuma_heartbeat_interval=75,
        removed_node_policy="pause",
        kuma_monitor_group="Proxy Nodes",
    )
    app.fetcher = FakeFetcher()
    app.repository = FakeRepository()
    app.management = object()
    app.status_page = FakeStatusPage()
    app.xray = FakeXray()
    app.last_subscription_success = None
    app.nodes = {}
    app.subscription_hash = None

    await app.sync_subscription(force=True)

    assert app.repository.upserted_names == ["Tokyo"]
    assert app.repository.disabled_keys == {"vless:🇺🇸 LA"}
    assert app.repository.active_keys == {"trojan:Tokyo"}
    assert len(app.xray.installed_config["inbounds"]) == 1
    assert app.xray.installed_config["outbounds"][0]["settings"]["servers"][0][
        "address"
    ] == "2001:db8::1"
    assert app.xray.restarted is True


@pytest.mark.asyncio
async def test_sync_subscription_accepts_valid_subscription_when_all_nodes_are_filtered(
    monkeypatch,
) -> None:
    monkeypatch.setattr("app.main.KumaReconciler", FakeReconciler)
    app = object.__new__(Application)
    app.settings = SimpleNamespace(
        subscription_url="https://example.test/sub",
        node_exclude_keywords=["la", "tokyo"],
        removed_node_grace_period=86400,
        monitor_name_prefix="Proxy",
        kuma_heartbeat_interval=75,
        removed_node_policy="pause",
        kuma_monitor_group="Proxy Nodes",
    )
    app.fetcher = FakeFetcher()
    app.repository = FakeRepository()
    app.management = object()
    app.status_page = FakeStatusPage()
    app.xray = FakeXray()
    app.last_subscription_success = None
    app.nodes = {}
    app.subscription_hash = None

    await app.sync_subscription(force=True)

    assert app.repository.upserted_names == []
    assert app.repository.disabled_keys == {"vless:🇺🇸 LA", "trojan:Tokyo"}
    assert app.repository.active_keys == set()
    assert app.xray.installed_config["inbounds"] == []
    assert app.xray.installed_config["outbounds"] == []
```

测试通过 Xray 配置中的唯一 Trojan outbound 证明只有 Tokyo 被纳入实际探测
配置；Kuma 对停用节点的立即暂停或删除行为继续由既有 `tests/test_kuma.py`
覆盖。

- [ ] **步骤 2：运行测试并确认按预期失败**

运行：

```bash
.venv/bin/pytest tests/test_application.py -q
```

预期：同步仍 upsert 两个节点，且未调用 `disable_nodes`。

- [ ] **步骤 3：编写最小接入实现**

在 `app/main.py` 导入 `partition_nodes`，解析后增加：

```python
nodes, excluded_nodes = partition_nodes(
    parsed.nodes, self.settings.node_exclude_keywords
)
records = [await self.repository.upsert_node(node) for node in nodes]
await self.repository.disable_nodes({node.node_key for node in excluded_nodes})
await self.repository.mark_missing(
    {node.node_key for node in nodes},
    self.settings.removed_node_grace_period,
)
```

后续 Xray 配置、`self.nodes`、日志节点数全部使用 `nodes`；日志增加
`excluded=%d`。订阅有效性判断继续使用 `parsed.nodes`，确保“订阅有效但全部被
过滤”与“订阅没有有效节点”语义不同。

- [ ] **步骤 4：运行同步、仓储、Kuma 与 Xray 相关测试**

运行：

```bash
.venv/bin/pytest tests/test_application.py tests/test_state.py tests/test_kuma.py tests/test_xray.py -q
```

预期：全部通过。

- [ ] **步骤 5：提交同步接入**

```bash
git add app/main.py tests/test_application.py
git commit -m "feat: 从探测与监控中立即排除节点"
```

### 任务 5：让探测请求全部 URL 并计算平均延迟

**文件：**

- 修改：`app/probe/checker.py`
- 创建：`tests/test_probe.py`

- [ ] **步骤 1：编写全部成功时的失败测试**

创建 `tests/test_probe.py`，先写可复用 fake：

```python
from types import SimpleNamespace

import httpx
import pytest

from app.probe.checker import ProbeChecker


class FakeAsyncClient:
    def __init__(self, outcomes: list[int | Exception]) -> None:
        self.outcomes = outcomes
        self.requested_urls: list[str] = []

    def factory(self, **kwargs):
        owner = self

        class Context:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, traceback) -> None:
                return None

            async def get(self, url: str):
                owner.requested_urls.append(url)
                outcome = owner.outcomes[len(owner.requested_urls) - 1]
                if isinstance(outcome, Exception):
                    raise outcome
                return SimpleNamespace(status_code=outcome)

        return Context()
```

然后增加全部成功测试：

```python
@pytest.mark.asyncio
async def test_check_requests_every_url_and_returns_average_latency(monkeypatch) -> None:
    client = FakeAsyncClient([204, 200])
    monkeypatch.setattr("app.probe.checker.httpx.AsyncClient", client.factory)
    times = iter([1.0, 1.1, 2.0, 2.3])
    monkeypatch.setattr("app.probe.checker.time.perf_counter", lambda: next(times))

    result = await ProbeChecker(10, 5, True).check(
        20000,
        [
            "https://cp.cloudflare.com/generate_204",
            "https://example.test/health",
        ],
    )

    assert client.requested_urls == [
        "https://cp.cloudflare.com/generate_204",
        "https://example.test/health",
    ]
    assert result.success is True
    assert result.total_time_ms == 200
    assert result.status_code == 200
```

- [ ] **步骤 2：运行测试并确认按预期失败**

运行：

```bash
.venv/bin/pytest tests/test_probe.py::test_check_requests_every_url_and_returns_average_latency -q
```

预期：现有实现只请求第一个 URL，且计时调用方式不符合独立计时。

- [ ] **步骤 3：编写最小成功路径实现**

将 `ProbeChecker.check` 的成功路径改为逐 URL 独立计时：

```python
latencies: list[float] = []
last_status: int | None = None
async with httpx.AsyncClient(
    proxy=f"socks5://127.0.0.1:{socks_port}",
    timeout=self.timeout,
    verify=self.tls_verify,
    follow_redirects=True,
) as client:
    for url in urls:
        started = time.perf_counter()
        response = await client.get(url)
        elapsed_ms = (time.perf_counter() - started) * 1000
        last_status = response.status_code
        expected = (
            response.status_code == 204
            if "generate_204" in url
            else 200 <= response.status_code < 400
        )
        if not expected:
            return ProbeResult(
                False, None, response.status_code, "HTTP_ERROR", datetime.now(UTC)
            )
        latencies.append(elapsed_ms)
return ProbeResult(
    True,
    round(sum(latencies) / len(latencies)),
    last_status,
    None,
    datetime.now(UTC),
)
```

- [ ] **步骤 4：运行成功路径测试并确认通过**

运行：

```bash
.venv/bin/pytest tests/test_probe.py::test_check_requests_every_url_and_returns_average_latency -q
```

预期：通过。

- [ ] **步骤 5：编写 HTTP 失败与异常失败测试**

增加 HTTP 状态失败、异常失败和单 URL 兼容测试：

```python
@pytest.mark.asyncio
async def test_check_fails_when_any_url_has_unexpected_status(monkeypatch) -> None:
    client = FakeAsyncClient([204, 500])
    monkeypatch.setattr("app.probe.checker.httpx.AsyncClient", client.factory)
    times = iter([1.0, 1.1, 2.0, 2.3])
    monkeypatch.setattr("app.probe.checker.time.perf_counter", lambda: next(times))

    result = await ProbeChecker(10, 5, True).check(
        20000,
        [
            "https://cp.cloudflare.com/generate_204",
            "https://example.test/health",
        ],
    )

    assert result.success is False
    assert result.total_time_ms is None
    assert result.status_code == 500
    assert result.error_category == "HTTP_ERROR"


@pytest.mark.asyncio
async def test_check_fails_without_partial_average_when_later_url_raises(monkeypatch) -> None:
    request = httpx.Request("GET", "https://example.test/health")
    client = FakeAsyncClient([204, httpx.ReadTimeout("timeout", request=request)])
    monkeypatch.setattr("app.probe.checker.httpx.AsyncClient", client.factory)
    times = iter([1.0, 1.1, 2.0])
    monkeypatch.setattr("app.probe.checker.time.perf_counter", lambda: next(times))

    result = await ProbeChecker(10, 5, True).check(
        20000,
        [
            "https://cp.cloudflare.com/generate_204",
            "https://example.test/health",
        ],
    )

    assert client.requested_urls == [
        "https://cp.cloudflare.com/generate_204",
        "https://example.test/health",
    ]
    assert result.success is False
    assert result.total_time_ms is None
    assert result.error_category == "TIMEOUT"


@pytest.mark.asyncio
async def test_check_single_url_returns_that_url_latency(monkeypatch) -> None:
    client = FakeAsyncClient([204])
    monkeypatch.setattr("app.probe.checker.httpx.AsyncClient", client.factory)
    times = iter([1.0, 1.125])
    monkeypatch.setattr("app.probe.checker.time.perf_counter", lambda: next(times))

    result = await ProbeChecker(10, 5, True).check(
        20000, ["https://cp.cloudflare.com/generate_204"]
    )

    assert result.success is True
    assert result.total_time_ms == 125
```

第二个 fake client 在第二次 `get` 抛出 `httpx.ReadTimeout`，并断言两个 URL
都已尝试。

- [ ] **步骤 6：运行失败路径测试并确认通过**

运行：

```bash
.venv/bin/pytest tests/test_probe.py -q
```

预期：全部通过。

- [ ] **步骤 7：提交探测改动**

```bash
git add app/probe/checker.py tests/test_probe.py
git commit -m "feat: 上报多 URL 平均探测延迟"
```

### 任务 6：更新环境变量示例和使用文档

**文件：**

- 修改：`.env.example`
- 修改：`README.md`

- [ ] **步骤 1：编写文档契约测试**

在 `tests/test_config.py` 增加：

```python
def test_env_example_documents_node_filter_and_multiple_test_urls() -> None:
    example = Path(".env.example").read_text()

    assert "NODE_EXCLUDE_KEYWORDS=" in example
    test_urls_line = next(
        line for line in example.splitlines() if line.startswith("TEST_URLS=")
    )
    assert "," in test_urls_line
```

导入 `pathlib.Path`。

- [ ] **步骤 2：运行测试并确认按预期失败**

运行：

```bash
.venv/bin/pytest tests/test_config.py::test_env_example_documents_node_filter_and_multiple_test_urls -q
```

预期：`.env.example` 尚无过滤配置，且 `TEST_URLS` 示例只有一个 URL。

- [ ] **步骤 3：更新示例和 README**

在 `.env.example` 中加入：

```dotenv
NODE_EXCLUDE_KEYWORDS=
TEST_URLS=https://cp.cloudflare.com/generate_204,https://www.gstatic.com/generate_204
```

README 环境变量表增加：

```markdown
| `NODE_EXCLUDE_KEYWORDS` | 空 | 逗号分隔；按节点名称忽略大小写包含匹配，命中后立即排除 |
| `TEST_URLS` | Cloudflare 204 | 逗号分隔；全部成功才成功，延迟取各 URL 平均值 |
```

并在工作原理或部署说明中注明：修改过滤关键字后需要重启 Agent；既有命中节点
会立即按 `REMOVED_NODE_POLICY` 暂停或删除。

- [ ] **步骤 4：运行文档契约测试并确认通过**

运行：

```bash
.venv/bin/pytest tests/test_config.py -q
```

预期：全部通过。

- [ ] **步骤 5：提交文档改动**

```bash
git add .env.example README.md tests/test_config.py
git commit -m "docs: 说明节点过滤与多 URL 探测配置"
```

### 任务 7：执行完整质量验证

**文件：**

- 检查：所有本次修改文件

- [ ] **步骤 1：运行完整测试**

```bash
.venv/bin/pytest
```

预期：全部测试通过，0 failed。

- [ ] **步骤 2：运行 Ruff**

```bash
.venv/bin/ruff check .
```

预期：`All checks passed!`

- [ ] **步骤 3：运行 mypy**

```bash
.venv/bin/mypy app
```

预期：`Success: no issues found`。

- [ ] **步骤 4：检查差异与工作区归属**

```bash
git diff --check
git status --short
git log --oneline -8
```

预期：无空白错误；本功能文件均已提交；用户原有的 `data/.gitkeep` 删除仍保持
未暂存且未被任何功能提交包含。
