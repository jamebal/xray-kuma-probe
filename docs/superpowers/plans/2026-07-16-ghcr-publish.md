# GitHub Container Registry 镜像发布实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**目标：** 使用 GitHub Actions 自动构建 amd64/arm64 Docker 镜像并发布到 GitHub Container Registry。

**架构：** 新增一个只负责容器发布的 workflow，通过 Docker 官方 Actions 完成 QEMU、Buildx、GHCR 登录、标签生成和 multi-platform 推送。使用 GitHub 原生 `GITHUB_TOKEN` 与 artifact attestation，不引入长期密钥。

**技术栈：** GitHub Actions、Docker Buildx、GitHub Container Registry、pytest。

---

### 任务一：锁定工作流发布契约

**文件：**
- 创建：`tests/test_github_actions.py`

- [x] **步骤一：编写失败测试**

```python
from pathlib import Path


def test_docker_publish_workflow_contract() -> None:
    workflow = Path(".github/workflows/docker-publish.yml").read_text()
    assert "packages: write" in workflow
    assert "secrets.GITHUB_TOKEN" in workflow
    assert "linux/amd64,linux/arm64" in workflow
```

- [x] **步骤二：运行测试并确认失败**

运行：`.venv312/bin/pytest tests/test_github_actions.py -q`

预期：因为 workflow 文件尚不存在而失败。

### 任务二：实现 GHCR multi-platform 发布

**文件：**
- 创建：`.github/workflows/docker-publish.yml`
- 测试：`tests/test_github_actions.py`

- [x] **步骤一：创建最小工作流**

工作流必须包含 `main`、`v*` 与手工触发，授予 Packages 和 attestation 权限，登录 `ghcr.io`，通过 metadata action 生成标签，并使用 Buildx 推送 amd64/arm64 manifest。

- [x] **步骤二：运行目标测试并确认通过**

运行：`.venv312/bin/pytest tests/test_github_actions.py -q`

预期：全部通过。

### 任务三：补充使用文档

**文件：**
- 修改：`README.md`

- [x] **步骤一：增加 GHCR 部署说明**

文档说明镜像地址、支持架构、自动标签，以及将 Compose 的 `build` 替换为 `image: ghcr.io/jamebal/xray-kuma-probe:latest` 的方式。

- [x] **步骤二：运行完整验证**

运行：

```bash
.venv312/bin/ruff check .
.venv312/bin/mypy app
.venv312/bin/pytest -q
docker buildx build --platform linux/amd64,linux/arm64 --check .
```

预期：所有命令退出码均为 0。

### 任务四：提交、合并与发布验证

**文件：**
- 提交上述全部新增和修改文件。

- [ ] **步骤一：检查差异与敏感信息**

运行：`git diff --check && git diff --stat && git status --short`

- [ ] **步骤二：创建提交并合并到 main**

提交信息：`ci: 发布多架构镜像到 GHCR`

- [ ] **步骤三：推送并观察首次 workflow**

运行：`git push origin main`，然后使用 GitHub CLI 检查 workflow run，确认 job 成功且 GHCR manifest 同时包含 amd64 与 arm64。
