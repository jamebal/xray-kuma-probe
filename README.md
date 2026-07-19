# xray-kuma-probe

`xray-kuma-probe` 是一个独立的代理节点监控 Agent。它定期下载 VLESS/Trojan 订阅，为每个节点生成独立的本地 SOCKS5 入口，通过 Xray-core 发起完整 HTTPS 请求，并自动创建及上报 Uptime Kuma Push Monitor。

## 工作原理

```text
订阅 URL -> 解析/稳定身份 -> SQLite 端口与 Monitor ownership
                         -> 单个 Xray 配置（每节点独立 inbound/route/outbound）
                         -> SOCKS5 -> HTTPS 测试 URL -> Kuma Push API
                         -> Kuma Socket.IO Internal API 创建/暂停 Monitor
```

Agent 只监听容器内 `127.0.0.1` 的 SOCKS 端口。订阅失败、空响应、HTML 登录页或没有有效节点时，会继续使用上一份配置，不会误删 Monitor。配置仅在订阅内容变化后生成，且必须通过 `xray run -test` 才原子替换并重启 Xray。

## 支持范围

- 订阅：Base64 多行文本、缺失 padding 的 Base64、纯文本、CRLF、BOM、Unicode 和 emoji 名称。
- 协议：VLESS、Trojan；其他协议只统计类型与数量。
- VLESS security：`none`、`tls`、`reality`。
- VLESS transport：`tcp`、`ws`、`grpc`、`httpupgrade`、`xhttp`/`splithttp`。
- VLESS 参数：`encryption`、`flow`、`sni`、`fp`、`alpn`、`pbk`、`sid`、`spx`、`host`、`path`、`serviceName`、`mode`、`authority`。
- Trojan：TLS 下的 `tcp`、`ws`、`grpc`、`httpupgrade`，以及 `sni`、`fp`、`alpn`、`host`、`path`、`serviceName`。

## 快速部署

要求 Docker Engine 24+、Docker Compose v2，并已有可登录的 Uptime Kuma 2.x 实例。

```bash
git clone https://github.com/jamebal/xray-kuma-probe.git
cd xray-kuma-probe
cp .env.example .env
$EDITOR .env
docker compose up -d --build
docker compose logs -f
```

Compose 会创建双栈 `probe` 网络。IPv4 地址池由 Docker 自动选择，IPv6 使用项目专用的 ULA subnet，避免与 NAS 上常见的既有 IPv4 Docker network 冲突。宿主机仍需具备可用的 IPv6 出站和 Docker IPv6/NAT66 支持。

### 使用 GitHub Container Registry 镜像

GitHub Actions 会将 `linux/amd64` 和 `linux/arm64` 镜像发布到 `ghcr.io/jamebal/xray-kuma-probe`。若不希望在部署设备上本地构建，可将 `compose.yaml` 中的：

```yaml
services:
  xray-kuma-probe:
    build: .
```

替换为：

```yaml
services:
  xray-kuma-probe:
    image: ghcr.io/jamebal/xray-kuma-probe:latest
```

然后拉取并启动：

```bash
docker compose pull
docker compose up -d
```

`main` 分支发布 `latest`、`main` 和 `sha-*` 标签；推送 `v1.2.3` 形式的 Git tag 时，还会发布 `1.2.3`、`1.2` 和 `1` 标签。生产环境建议固定到版本标签，避免 `latest` 更新带来未计划的变更。

至少填写 `SUBSCRIPTION_URL`、`KUMA_URL`、`KUMA_USERNAME`、`KUMA_PASSWORD`。Kuma 地址必须从 Agent 容器可访问；若 Kuma 在同一个 Compose 网络中，使用服务名，不要使用容器内的 `localhost`。

## 环境变量

| 变量 | 默认值 | 说明 |
|---|---:|---|
| `KUMA_STATUS_PAGE_SLUG` | 空 | 空时不管理 Status Page |
| `MONITOR_NAME_PREFIX` | `Proxy` | ownership 名称前缀；实际 ownership 以 SQLite 为准 |
| `KUMA_MONITOR_GROUP` | `Proxy Nodes` | Kuma 左侧 Monitor 树分组；留空禁用 |
| `PROBE_INTERVAL` | `60` | 探测周期，秒 |
| `KUMA_HEARTBEAT_INTERVAL` | `75` | Kuma 无心跳判定窗口，必须大于探测周期 |
| `SUBSCRIPTION_SYNC_INTERVAL` | `300` | 订阅同步周期，秒 |
| `PROBE_TIMEOUT` / `PROBE_CONNECT_TIMEOUT` | `10` / `5` | 总超时与连接超时 |
| `PROBE_CONCURRENCY` | `10` | 最大并发探测数 |
| `FAILURE_THRESHOLD` / `RECOVERY_THRESHOLD` | `2` / `1` | DOWN/UP 防抖阈值 |
| `TEST_URLS` | Cloudflare 204 | 逗号分隔；全部成功才成功，延迟取各 URL 平均值；`generate_204` 要求 204，其他 URL 接受 200-399 |
| `NODE_EXCLUDE_KEYWORDS` | 空 | 逗号分隔；按节点名称忽略大小写包含匹配，命中后立即排除 |
| `SOCKS_PORT_START` / `SOCKS_PORT_END` | `20000` / `29999` | 容器内稳定端口池 |
| `REMOVED_NODE_POLICY` | `pause` | 可选 `pause` 或 `delete` |
| `REMOVED_NODE_GRACE_PERIOD` | `86400` | 消失节点宽限期，秒 |
| `TLS_VERIFY` | `true` | 订阅、Kuma、探测的 TLS 校验 |
| `DATABASE_PATH` | `/app/data/state.db` | SQLite 路径 |
| `HEALTH_LISTEN` / `HEALTH_PORT` | `0.0.0.0` / `8080` | 健康检查监听 |

完整项目参数均列在 `.env.example`。

修改 `NODE_EXCLUDE_KEYWORDS` 后需要重启 Agent。既有 Monitor 一旦命中关键字，
会立即按 `REMOVED_NODE_POLICY` 暂停或删除，不等待
`REMOVED_NODE_GRACE_PERIOD`；新命中节点不会占用 SOCKS 端口或加入监控。

## Uptime Kuma 与 Status Page

账号需要创建、编辑、暂停 Push Monitor 的权限。项目只操作 SQLite 中登记的 Monitor ID，即使存在同名手工 Monitor 也不会接管。Kuma API key 只能用于 `/metrics`，不能认证 Socket.IO Internal API；`KUMA_USERNAME` 和 `KUMA_PASSWORD` 必须填写真实登录账号，不能用 API key 替代。

填写 `KUMA_STATUS_PAGE_SLUG` 后会启用可选 Status Page 同步。Uptime Kuma 的 Status Page Internal API 并非稳定公开 API，各版本 payload 可能不同；同步失败只记录 `status_page_sync_failed`，不会停止 Monitor 创建、探测或 Push。核心集成已按 Uptime Kuma 2.4.0 的 Socket.IO event 与 Monitor payload 验证，升级 Kuma 后仍建议先在测试实例验证。

## 状态、日志与健康检查

```bash
docker compose logs -f xray-kuma-probe
curl http://127.0.0.1:8080/health
```

日志不会输出订阅 URL、完整节点 URI、UUID、Trojan password 或 Kuma 密码。Kuma 消息只包含 `HTTP 204`、`TIMEOUT`、`TLS_FAILED` 等简化状态。

## 升级与备份

```bash
cp data/state.db data/state.db.backup
git pull --ff-only
docker compose up -d --build
```

备份 `data/state.db` 可保留稳定端口、Monitor ownership 和防抖状态；同时备份 `.env`，但不要提交它。`generated/xray.json` 含节点凭据，必须按敏感文件保护，不应公开备份。

## 常见错误

- `subscription_fetch_failed`：检查 URL、容器 DNS、证书与订阅是否返回 HTML/空内容。
- `xray_config_invalid`：节点参数不受当前 Xray 版本支持；旧配置仍继续运行。
- `Kuma API 调用失败`：确认地址、账号、反向代理 WebSocket 和 Kuma 版本。
- `unable to open database file`：旧镜像在 fnOS/NAS 的 root-owned bind mount 上可能无写权限；更新镜像后 entrypoint 会自动修正 `data` 和 `generated` ownership，再以非 root 用户启动 Agent。
- `SOCKS 端口池已耗尽`：扩大端口区间后重启；端口只在容器内绑定回环地址。
- 健康检查显示 `xray=stopped`：检查订阅是否至少包含一个有效节点，以及 Xray 校验日志。

## 本地开发

```bash
python3.12 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/ruff check .
.venv/bin/mypy app
.venv/bin/pytest
```

## 安全说明

容器以非 root 用户运行，不使用 privileged、host network 或 Docker Socket，也不读写 Kuma SQLite。`data/` 与 `generated/` 应限制宿主机权限。生产环境不要关闭 `TLS_VERIFY`，并为 Agent 使用权限受控的 Kuma 专用账号。

项目采用 MIT License。
