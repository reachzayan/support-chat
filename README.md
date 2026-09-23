# SupportChat

SupportChat is an embeddable live-chat product for Sample Services marketing sites (SampleSite, Sample Services, and related properties). Visitors chat through a third-party widget on the host page. A grounded bot answers from a per-site knowledge base. Staff join from an admin inbox when a conversation needs a human.

The stack is a FastAPI backend, Next.js staff app and widget surfaces, PostgreSQL (with pgvector), and Redis for pub/sub and rate limiting.

## Repository layout

```
backend/          FastAPI API, WebSockets, KB ingest workers, Alembic migrations
frontend/         Next.js 16 app (staff admin, widget iframe, embed loader)
deploy/           EC2 bootstrap, nginx template, GitHub Actions SSM deploy scripts
docker-compose.yml          Local full stack (Postgres, Redis, API, worker, frontend)
docker-compose.prod.yml     Production overlay (TLS Redis, split API/worker, host binding)
```

Only `backend/`, `frontend/`, `deploy/`, `.github/`, and a small set of root files are versioned. Copy `.env.example` and `backend/.env.example` locally; never commit secrets or transcript exports.

## Branch model

| Branch    | Role |
|-----------|------|
| `dev`     | Day-to-day integration. CI runs on every push and PR. Merges here deploy to the dev EC2 instance. |
| `staging` | Pre-production. Promote tested `dev` work here before production. |
| `main`    | Production line. Only release-ready commits. |

Typical flow: feature branch → PR into `dev` → validate on dev host → merge `dev` into `staging` → after sign-off, merge `staging` into `main`.

`master` is legacy and should not receive new work.

## Architecture

### Surfaces

The backend enforces host-based surface separation:

- **Staff app** (`STAFF_APP_ORIGIN`) — agent inbox, sites, knowledge, logs, settings. Invite-only JWT auth with rotating refresh cookies and CSRF on mutating routes.
- **Widget** (`WIDGET_ORIGIN`) — visitor chat UI loaded in a cross-origin iframe. Origin-allowlisted per `site_key`.
- **Marketing host** (`MARKETING_HOST_ORIGIN`) — demo and marketing pages that load the embed loader.

Public widget endpoints validate the caller origin against each site's allowlist. Admin APIs require an authenticated staff session.

### Widget embed

The host page loads `supportchat.js` (built from `frontend/embed-loader/`). The loader renders a launcher and opens a cross-origin iframe pointed at the widget origin. Visitor identity is scoped to `site_key` and stored in the iframe origin (with an optional first-party cookie on the host via the loader). Identity does not leak across sites.

Host CSS does not style the transcript; the panel is fully isolated in the iframe.

### Chat runtime

- Postgres stores conversations, messages, visitors, handoffs, and KB data.
- WebSockets carry live transcript and state to visitors and agents.
- Redis pub/sub fans out events across API processes.
- When an agent joins, the bot stops generating for that conversation.
- Background workers (separate Compose service in production) run KB ingest, idle-close, and maintenance purges.

### Knowledge base

Sources are crawled or fetched, chunked, embedded (OpenAI), and indexed in Postgres/pgvector. The bot retrieves evidence, cites KB chunks, and refuses requests for SSN, driver license, plate, or medical details. Legacy article CRUD under `/api/sites/{id}/articles` is deprecated; use KB source APIs.

## Prerequisites

- Docker Engine with Compose v2
- Node.js 22 and npm (frontend development and CI parity)
- [uv](https://docs.astral.sh/uv/) 0.11.x (backend)
- PostgreSQL client optional; tests expect Postgres reachable on `127.0.0.1:55432` when not using Compose defaults

For bot replies and KB ingest you also need:

- `ANTHROPIC_API_KEY` — conversation generation
- `OPENAI_API_KEY` — query and ingest embeddings

## Local setup

### 1. Environment files

```bash
cp .env.example .env
cp backend/.env.example backend/.env
```

Edit both files. At minimum set unique 64+ character values for `JWT_SECRET`, `WIDGET_TOKEN_SECRET`, `RATE_KEY_SECRET`, and `WIDGET_CSP_SERVICE_SECRET`. Add API keys when exercising the bot or KB pipeline.

### 2. Full stack with Docker

From the repository root:

```bash
cd backend && ./scripts/docker_up.sh
```

This builds and starts Postgres (port `55432`), Redis (`56379`), the API (`8000`), a background worker, and the frontend (`3000`). The API container runs Alembic migrations and seeds a default staff user on first boot.

### 3. Host-run API (optional)

With Compose Postgres and Redis already up:

```bash
cd backend
uv sync --frozen
uv run alembic upgrade head
uv run python -m scripts.seed_user   # once
uv run fastapi dev --host 0.0.0.0 --port 8000
```

```bash
cd frontend
npm ci
npm run dev
```

Point `DATABASE_URL` and `REDIS_URL` in `backend/.env` at the Compose ports (`55432` / `56379`).

### 4. Local hostnames

Default origins use `localhost` subdomains for surface testing:

| Variable | Default |
|----------|---------|
| `STAFF_APP_ORIGIN` | `http://localhost:3000` |
| `WIDGET_ORIGIN` | `http://widget.localhost:3000` |
| `MARKETING_HOST_ORIGIN` | `http://host.localhost:3000` |

Map these in `/etc/hosts` or use a DNS helper if your browser requires it.

### 5. Staff login

After seeding, sign in at `/login` with the credentials created by `backend/scripts/seed_user.py` (see script for defaults in local environments).

## Running tests

### Backend

Postgres database name must contain `test` (default `support_chat_test`). CI uses port `5432`; local Compose maps `55432`.

```bash
cd backend
uv run ruff check .
uv run ruff format --check .
CI=true uv run pytest
```

### Frontend

```bash
cd frontend
npm run lint
npm run typecheck
npm test
npm run build
```

### CI locally

```bash
bash deploy/verify-ci-checks.sh
```

## Database migrations

```bash
cd backend
uv run alembic upgrade head
uv run alembic revision --autogenerate -m "describe change"
```

Migrations live in `backend/alembic/versions/`. Production schema changes go through Alembic only.

## Configuration reference

Key settings (see `backend/.env.example` for the full list):

| Variable | Purpose |
|----------|---------|
| `APP_ENV` | `local`, `staging`, or `production`. Production enforces secure cookies and required secrets. |
| `ENABLE_BACKGROUND_WORKERS` | `false` on API containers, `true` on the worker service in Compose prod. |
| `CHAT_RETENTION_DAYS` | Conversation retention window. |
| `MESSAGE_REPLAY_LIMIT` | Max messages replayed per WebSocket catch-up batch. |
| `TRUSTED_PROXY_CIDRS` | CIDRs allowed to set forwarded client IP headers. |

Frontend build-time public URLs use the `NEXT_PUBLIC_*` variables in `.env.example`.

## Production deployment

Dev deploys automatically from `dev` via GitHub Actions (`.github/workflows/ci-cd.yml`): backend and frontend CI, then SSM deploy to EC2 (`deploy/github-actions-ssm-deploy.sh`).

First-time instance setup:

1. Clone the repo on the EC2 host.
2. Fill `.env` and `backend/.env.prod` from the `*.example` templates.
3. Run `deploy/bootstrap-ec2.sh` with `STAFF_HOST`, `WIDGET_HOST`, `MARKETING_HOST`, and `LETSENCRYPT_EMAIL`.
4. Start with `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build`.

Production runs API and worker containers separately. Redis uses TLS with a mounted CA (`deploy/generate-redis-tls.sh`).

## Operational scripts

| Script | Purpose |
|--------|---------|
| `backend/scripts/purge_expired_chats.py` | Enforce chat retention |
| `backend/scripts/purge_expired_logs.py` | Trim old application logs |
| `backend/scripts/purge_expired_refresh_tokens.py` | Remove expired refresh tokens |
| `backend/scripts/run_samplesite_eval.py` | Offline eval against golden sets |

Run maintenance scripts via the worker container or a one-off `uv run` with production env loaded.

## Security and compliance

- Transcripts may contain candidate and employer PII governed by FCRA/DOT policies. Do not log message bodies, prompts with visitor text, or exports in unsecured channels.
- Widget and admin surfaces are isolated by host and `site_key`. Do not share visitor identity across SampleSite and Sample Services sites.
- Rate limits apply to bootstrap, visitor creation, message submit, login failures, and widget CSP endpoints.
- KB crawl and fetch paths block SSRF targets (private IPs, metadata endpoints, file schemes).

## License

Proprietary — Sample Services. All rights reserved.
