"""S5：部署产物结构与健康配置校验。"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_dockerfile_multi_stage_and_non_root():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "AS builder" in dockerfile
    assert "AS runtime" in dockerfile
    assert "USER appuser" in dockerfile
    assert "HEALTHCHECK" in dockerfile
    assert "entrypoint.sh" in dockerfile


def test_gunicorn_config_exists():
    conf = ROOT / "docker" / "gunicorn_conf.py"
    assert conf.is_file()
    text = conf.read_text(encoding="utf-8")
    assert "UvicornWorker" in text
    assert "graceful_timeout" in text


def test_kubernetes_manifests_present():
    k8s = ROOT / "deploy" / "kubernetes"
    for name in ("deployment.yaml", "service.yaml", "configmap.yaml", "secret.example.yaml"):
        assert (k8s / name).is_file(), f"missing {name}"


def test_smoke_script_exists():
    script = ROOT / "scripts" / "smoke_deploy.sh"
    assert script.is_file()
    assert "health/ready" in script.read_text(encoding="utf-8")


def test_compose_uses_pgvector():
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert "pgvector/pgvector" in compose
    assert "milvus" not in compose.lower()
