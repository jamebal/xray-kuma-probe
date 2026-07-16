from pathlib import Path

WORKFLOW_PATH = Path(".github/workflows/docker-publish.yml")


def test_docker_publish_workflow_contract() -> None:
    workflow = WORKFLOW_PATH.read_text()

    assert "ghcr.io" in workflow
    assert "packages: write" in workflow
    assert "attestations: write" in workflow
    assert "id-token: write" in workflow
    assert "secrets.GITHUB_TOKEN" in workflow
    assert "linux/amd64,linux/arm64" in workflow

    assert "branches:" in workflow
    assert "- main" in workflow
    assert "tags:" in workflow
    assert '- "v*"' in workflow
    assert "workflow_dispatch:" in workflow

    assert "docker/metadata-action@v6" in workflow
    assert "docker/build-push-action@v7" in workflow
    assert "actions/attest@v4" in workflow
    assert "type=raw,value=latest,enable={{is_default_branch}}" in workflow
    assert "type=semver,pattern={{version}}" in workflow
    assert "type=sha" in workflow


def test_docker_publish_workflow_does_not_contain_hardcoded_credentials() -> None:
    workflow = WORKFLOW_PATH.read_text()
    password_lines = [
        line.strip() for line in workflow.splitlines() if line.strip().startswith("password:")
    ]

    assert "ghp_" not in workflow.lower()
    assert "github_pat_" not in workflow.lower()
    assert password_lines == ["password: ${{ secrets.GITHUB_TOKEN }}"]
