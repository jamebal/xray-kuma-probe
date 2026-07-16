# Trojan TLS 参数兼容实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**目标：** 正确映射 Trojan/VLESS 订阅中的 `allowInsecure` 与 `peer` 参数，使明确要求跳过证书校验的节点可被 Xray 正常探测。

**架构：** 保持现有 parser 的原始 query 参数模型不变，只在 Xray 配置边界完成字符串到布尔值的转换。TLS `serverName` 继续优先使用 `sni`，新增 `peer` 兼容回退，不改变缺失参数时的安全默认行为。

**技术栈：** Python 3.12、pytest、Xray-core、Docker Compose。

---

### 任务 1：增加回归测试

**文件：**
- 修改：`tests/test_xray.py`

- [x] 增加 `allowInsecure` 真值、假值、缺失值测试。
- [x] 增加 `sni` 优先和 `peer` 回退测试。
- [x] 运行目标测试，确认现有实现失败。

### 任务 2：实现最小修复

**文件：**
- 修改：`app/xray/config_builder.py`

- [x] 增加订阅布尔值转换函数。
- [x] 仅在参数存在时写入 `tlsSettings.allowInsecure`。
- [x] 将 `serverName` 回退顺序调整为 `sni`、`peer`、`host`。
- [x] 运行目标测试，确认修复通过。

### 任务 3：完整验证与交付

**文件：**
- 验证：`app/xray/config_builder.py`
- 验证：`tests/test_xray.py`

- [x] 运行 `ruff check .`。
- [x] 运行 `mypy app`。
- [x] 运行 `pytest -q`。
- [x] 构建 Docker 镜像。
- [x] 使用真实订阅配置执行临时 HTTP 204 回归测试。
- [x] 检查 Git 差异，不包含敏感文件。
- [ ] 提交并推送 `main`。
