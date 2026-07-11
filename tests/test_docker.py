from pathlib import Path


def test_container_repairs_volume_permissions_then_drops_privileges() -> None:
    dockerfile = Path("Dockerfile").read_text()
    entrypoint = Path("docker-entrypoint.sh").read_text()

    assert "gosu" in dockerfile
    assert "USER root" in dockerfile
    assert 'ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]' in dockerfile
    assert "chown -R probe:probe /app/data /app/generated" in entrypoint
    assert 'exec gosu probe "$@"' in entrypoint
