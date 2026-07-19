# 节点过滤与多 URL 平均延迟设计

## 目标

为订阅节点增加基于名称关键字的排除能力，使命中关键字的节点不进入 Xray
探测配置和 Uptime Kuma 监控；同时让 `TEST_URLS` 对所有配置 URL 执行探测，
仅在全部成功时上报成功，并上报各 URL 请求延迟的算术平均值。

## 配置

新增环境变量 `NODE_EXCLUDE_KEYWORDS`，默认值为空。该变量使用逗号分隔，
与 `TEST_URLS` 的配置形式一致，例如：

```dotenv
NODE_EXCLUDE_KEYWORDS=Expire,官网,剩余流量
TEST_URLS=https://cp.cloudflare.com/generate_204,https://example.com/health
```

配置解析时去除每个值首尾的空白并忽略空项。节点过滤只检查
`ProxyNode.display_name`，采用 Unicode 字符串的忽略大小写包含匹配。
因此关键字 `expire` 可以匹配 `Node-EXPIRE-01`。

`TEST_URLS` 已支持逗号分隔解析，本次不改变其配置格式。配置必须至少包含一个
非空 URL，避免没有实际请求时产生错误的成功结果。

## 节点过滤数据流

订阅内容仍由 `parse_subscription` 完整解析。过滤发生在 `Application` 的订阅同步
流程中，不让通用订阅解析器依赖运行时配置：

1. 解析订阅得到全部有效节点。
2. 按 `NODE_EXCLUDE_KEYWORDS` 将节点拆分为保留节点和排除节点。
3. 只对保留节点执行 `upsert_node`，只用保留节点生成 Xray 配置。
4. 对数据库中与排除节点 `node_key` 相同的既有记录执行立即停用。
5. 对订阅中真正消失的节点继续使用 `REMOVED_NODE_GRACE_PERIOD`。
6. Kuma Reconciler 根据停用状态立即执行 `REMOVED_NODE_POLICY`：
   `pause` 时暂停，`delete` 时删除。

立即停用操作由 `NodeRepository` 提供独立接口，明确区别于带宽限期的
`mark_missing`。新出现但已命中过滤规则的节点不会写入数据库、占用 SOCKS
端口、创建 Kuma Monitor 或加入 Status Page。

如果过滤后没有保留节点，本次同步仍视为有效配置变更：所有已知命中节点立即
停用，Xray 安装一个不包含节点入口的有效配置。原有“订阅中没有任何有效
VLESS/Trojan 节点时保留旧配置”的保护逻辑不变，因为过滤发生在确认订阅至少
包含一个有效节点之后。

订阅内容哈希不能单独决定是否跳过同步，因为用户可能只修改过滤关键字后重启
进程。首次强制同步总会应用当前过滤规则；同一进程内配置不会动态变化，因此
后续仍可使用现有订阅哈希快速跳过。

同步日志增加排除节点数量，但不输出关键字或节点凭据。

## 多 URL 探测数据流

`ProbeChecker.check` 复用一个经节点 SOCKS5 代理连接的 `httpx.AsyncClient`，
按配置顺序逐个请求 URL。每次请求前后分别读取单调时钟，获得该 URL 的独立
耗时。

成功规则保持现有约定：

- URL 包含 `generate_204` 时要求 HTTP 204。
- 其他 URL 接受 HTTP 200–399。

任意 URL 请求抛出异常或返回不合格状态码时，整次节点探测立即失败。失败结果
沿用现有错误分类；HTTP 状态不合格时返回 `HTTP_ERROR`。失败结果不计算部分
平均值，`total_time_ms` 为 `None`，避免把不完整样本上报为节点延迟。

只有全部 URL 成功时，才将每个 URL 的毫秒耗时求算术平均值并四舍五入为整数，
写入 `ProbeResult.total_time_ms`。单 URL 配置自然得到该 URL 的延迟，保持兼容。

请求采用顺序执行，避免每个节点同时放大外部请求并突破现有
`PROBE_CONCURRENCY` 的容量预期。`httpx.Timeout` 继续对每个请求生效。

## 错误处理与状态一致性

- 配置中的空关键字被忽略；空关键字数组表示不过滤任何节点。
- `TEST_URLS` 为空时由配置校验拒绝启动。
- 过滤节点的 Kuma 操作失败时沿用现有 `kuma_reconcile_failed` 行为；节点已在
  本地标记为停用，因此不会继续被 Probe Scheduler 探测。
- Xray 新配置安装失败时沿用现有原子替换保护。数据库与 Kuma 已停用的过滤节点
  不会重新启用，避免继续监控用户明确排除的节点。
- `asyncio.CancelledError` 继续向上传播，不转换为探测失败。

## 测试

测试按 TDD 增加以下行为覆盖：

- `NODE_EXCLUDE_KEYWORDS` 的逗号分隔、去空白、忽略空项和默认空数组。
- `TEST_URLS` 拒绝空列表。
- 节点名称的忽略大小写包含匹配及不匹配行为。
- 仓储层立即停用指定节点，不影响普通消失节点的宽限期。
- 订阅同步只为保留节点生成记录和 Xray 配置，既有过滤节点立即停用。
- 全部测试 URL 成功时请求全部 URL，并返回独立耗时的平均值。
- 任一 URL 返回错误状态或抛出异常时整次失败且不返回部分平均值。
- 单 URL 探测行为保持兼容。

完成后运行 `pytest`、`ruff check .` 和 `mypy app` 进行完整验证。
