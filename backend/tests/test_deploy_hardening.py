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


def test_deploy_uses_actions_token_https_fetch_not_ssh_deploy_key() -> None:
    deploy = _read("deploy/ssm-deploy.sh")
    sender = _read("deploy/github-actions-ssm-deploy.sh")
    ci = _read(".github/workflows/ci-cd.yml")
    manual = _read(".github/workflows/deploy-dev.yml")
    assert "x-access-token:${GITHUB_TOKEN}@github.com" in deploy
    assert "git@github.com" not in deploy
    assert "deploy key" not in deploy.lower()
    assert "GITHUB_TOKEN" in sender
    assert "GITHUB_TOKEN: ${{ github.token }}" in ci
    assert "GITHUB_TOKEN: ${{ github.token }}" in manual


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


def test_migrate_service_mounts_redis_ca_like_backend() -> None:
    """Prod migrate loads rediss:// from .env.prod; without the CA mount the
    shared entrypoint times out on Redis and never runs Alembic."""
    compose = _read("docker-compose.prod.yml")
    migrate_block = compose.split("migrate:", 1)[1].split("\n  worker:", 1)[0]
    assert "/run/secrets/redis-ca.crt:ro" in migrate_block


def test_entrypoint_skips_redis_wait_for_migrate_command() -> None:
    entrypoint = _read("backend/docker/entrypoint.sh")
    assert "migrate.sh" in entrypoint
    assert "Waiting for Redis..." in entrypoint


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


def test_production_backend_drops_capabilities_like_the_worker() -> None:
    compose = _read("docker-compose.prod.yml")
    backend_block = compose.split("backend:", 1)[1].split("\n  migrate:", 1)[0]
    assert 'cap_drop: ["ALL"]' in backend_block
    assert "no-new-privileges:true" in backend_block


def test_frontend_has_a_loopback_healthcheck() -> None:
    compose = _read("docker-compose.yml")
    frontend_block = compose.split("frontend:", 1)[1]
    assert "healthcheck:" in frontend_block
    assert "127.0.0.1:3000/login" in frontend_block


def test_local_compose_publishes_only_on_loopback() -> None:
    compose = _read("docker-compose.yml")
    assert '"127.0.0.1:${POSTGRES_PORT:-55432}:5432"' in compose
    assert '"127.0.0.1:${REDIS_PORT:-56379}:6379"' in compose
    assert '"127.0.0.1:${BACKEND_PORT:-8000}:8000"' in compose
    assert '"127.0.0.1:${FRONTEND_PORT:-3000}:3000"' in compose


def test_docker_up_starts_the_repo_root_stack() -> None:
    script = _read("backend/scripts/docker_up.sh")
    assert '$(dirname "$0")/../..' in script
    assert not (ROOT / "backend" / "docker-compose.yml").exists()


def test_production_env_example_trusts_only_the_compose_gateway() -> None:
    example = _read("backend/.env.prod.example")
    assert "TRUSTED_PROXY_CIDRS=172.18.0.1/32" in example
