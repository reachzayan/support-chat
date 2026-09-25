from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text()


def test_deploy_always_updates_the_worker_service() -> None:
    deploy = _read("deploy/ssm-deploy.sh")
    sender = _read("deploy/github-actions-ssm-deploy.sh")
    assert "COMPOSE_APP_SERVICES:-backend worker frontend" in deploy
    assert "COMPOSE_APP_SERVICES:-backend worker frontend" in sender


def test_deploy_fails_unless_required_services_become_healthy() -> None:
    deploy = _read("deploy/ssm-deploy.sh")
    assert "up --build -d --wait --wait-timeout 180" in deploy


def test_frontend_pins_turbopack_to_the_frontend_package() -> None:
    config = _read("frontend/next.config.ts")
    assert "turbopack:" in config
    assert "fileURLToPath(import.meta.url)" in config


def test_deploy_command_never_transports_a_github_token() -> None:
    files = (
        "deploy/ssm-deploy.sh",
        "deploy/github-actions-ssm-deploy.sh",
        ".github/workflows/ci-cd.yml",
        ".github/workflows/deploy-dev.yml",
    )
    for relative in files:
        assert "GITHUB_TOKEN" not in _read(relative), relative


def test_production_redis_uses_acl_app_identity() -> None:
    compose = _read("docker-compose.prod.yml")
    entrypoint = _read("deploy/redis-secure-entrypoint.sh")
    assert "--aclfile" in entrypoint
    assert "user default off" in entrypoint
    assert "user app on" in entrypoint
    assert "+select" in entrypoint
    assert "+hello" in entrypoint
    assert "REDIS_APP_PASSWORD" in compose
    assert "rediss://app:" in _read("backend/.env.prod.example")
    assert "rediss://app:" in _read("backend/.env.example")


def test_deploy_workflows_pin_the_worker_service_list() -> None:
    for relative in (".github/workflows/ci-cd.yml", ".github/workflows/deploy-dev.yml"):
        workflow = _read(relative)
        assert "COMPOSE_APP_SERVICES: backend worker frontend" in workflow, relative


def test_backend_container_runs_as_non_root() -> None:
    dockerfile = _read("backend/Dockerfile")
    assert "USER app" in dockerfile


def test_runtime_database_role_is_not_the_migration_or_admin_role() -> None:
    compose = _read("docker-compose.yml")
    assert "APP_DB_USER" in compose
    assert "MIGRATION_DB_USER" in compose
    assert "service_completed_successfully" in compose
    assert "alembic upgrade head" not in _read("backend/docker/entrypoint.sh")
    provision = _read("deploy/provision-postgres-roles.sh")
    assert "REVOKE CREATE ON SCHEMA public FROM PUBLIC" in provision
    assert "ALTER DEFAULT PRIVILEGES" in provision
    assert "GRANT EXECUTE ON ALL FUNCTIONS" in provision
    assert "GRANT USAGE ON ALL TYPES" in provision


def test_edge_sets_transport_and_capability_headers() -> None:
    nginx = _read("deploy/nginx.conf.template")
    assert "Strict-Transport-Security" in nginx
    assert "Permissions-Policy" in nginx
    assert "client_max_body_size 4k;" in nginx
