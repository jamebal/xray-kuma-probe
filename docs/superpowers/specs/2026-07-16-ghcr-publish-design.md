# GitHub Container Registry 镜像发布设计

## 目标

通过 GitHub Actions 自动构建并发布 `ghcr.io/jamebal/xray-kuma-probe`，让使用者无需在部署设备上编译镜像，并同时支持常见的 x86_64 与 ARM64 主机。

## 触发与标签

- 推送到 `main`：发布 `latest`、`main` 和提交短 SHA 标签。
- 推送 `v*` Git tag：发布完整 SemVer、主次版本、主版本和提交短 SHA 标签。
- `workflow_dispatch`：允许在 GitHub 页面手工重新构建当前 ref。

镜像名称直接使用 `${{ github.repository }}`，避免仓库迁移或 fork 后仍向旧命名空间推送。

## 构建架构

单个 job 在 GitHub 托管的 Ubuntu runner 上配置 QEMU 与 Docker Buildx，通过现有 `Dockerfile` 的 `TARGETARCH` 分支构建：

- `linux/amd64`
- `linux/arm64`

构建层写入 GitHub Actions cache，以缩短后续构建时间。构建成功后一次性推送 multi-platform manifest，避免出现只有单一架构的临时标签。

## 权限与供应链

工作流只授予所需权限：读取仓库、写入 Packages、写入 artifact attestation，并通过 OIDC 生成证明。登录 GHCR 使用运行时提供的 `GITHUB_TOKEN`，仓库中不保存 PAT 或其他密钥。

构建完成后为推送的镜像 digest 生成 build provenance attestation，并将证明关联到 GHCR 镜像。

## 文档与验证

README 增加直接拉取 GHCR 镜像的 Compose 配置说明，以及 tag 与支持架构说明。测试以文本方式验证 workflow 的关键安全和发布契约，避免为项目额外引入 YAML 解析依赖。
