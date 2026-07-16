# Trojan TLS 参数兼容设计

## 背景

当前订阅中的 Trojan 节点均携带 `allowInsecure=1`、`peer` 和 `sni` 参数。配置生成器只写入 `serverName` 与 `fingerprint`，导致 Xray 使用默认的严格证书校验。实测同一节点在 `allowInsecure=false` 时返回 `ConnectError`，在 `allowInsecure=true` 时返回 HTTP 204。

## 目标

- 将订阅中的 `allowInsecure` 安全地映射到 Xray `tlsSettings.allowInsecure`。
- 保持未声明 `allowInsecure` 的节点继续使用 Xray 默认严格校验。
- 优先使用 `sni`，仅在 `sni` 缺失时使用 `peer` 作为 `serverName` 回退值。
- 不输出或提交订阅凭据、服务器地址及完整节点 URI。

## 方案

在 `app/xray/config_builder.py` 增加一个只识别明确真值的内部转换函数。接受 `1`、`true`、`yes`、`on`，忽略大小写和首尾空白；其他值均视为假。

生成 TLS 配置时：

1. `serverName` 按 `sni`、`peer`、`host` 的顺序选择。
2. 仅当订阅中存在 `allowInsecure` 参数时，才写入布尔类型的 `allowInsecure`。
3. 保留现有 `fingerprint` 和 `alpn` 行为。

## 测试

- `allowInsecure=1` 生成 `true`。
- `allowInsecure=false` 生成 `false`。
- 参数缺失时不生成 `allowInsecure` 字段。
- `sni` 缺失时使用 `peer`，`sni` 存在时优先使用 `sni`。
- 完整执行 `ruff check .`、`mypy app`、`pytest -q`、Docker 镜像构建。
- 使用真实订阅生成的配置进行一次性容器连接测试，期望 HTTP 204。

## 非目标

- 不改变全局 `TLS_VERIFY` 的语义。
- 不修改 Kuma Monitor、scheduler、防抖或订阅同步逻辑。
- 不把 `allowInsecure` 默认开启。
