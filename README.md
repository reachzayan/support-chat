# Support Chat

An embeddable support chat widget with a staff inbox and a knowledge-backed assistant. Built with FastAPI, Next.js, PostgreSQL with pgvector, and Redis.

## Features

- Visitor chat with returning-session context and staff handoff.
- Staff inbox, notifications, workspace search, and canned replies.
- Knowledge ingestion and grounded assistant responses.
- Site configuration, rate limits, and conversation retention.
- Responsive staff consoles and an embeddable widget loader.

## Layout

- `backend/`: API, workers, database migrations, and Python tests.
- `frontend/`: staff console, visitor widget, embed loader, and frontend tests.
- `deploy/`: infrastructure and deployment helpers.

## Local setup

Install Docker with Compose. Copy `backend/.env.example` to `backend/.env` and configure local values. Provide independent random values for `JWT_SECRET`, `WIDGET_TOKEN_SECRET`, `RATE_KEY_SECRET`, and `WIDGET_CSP_SERVICE_SECRET` in your shell or a root `.env` file; Compose requires them. Add model API credentials to `backend/.env` if you want assistant features.

```bash
cp backend/.env.example backend/.env
# Configure environment values before starting.
docker compose up --build
```

The frontend runs at `http://localhost:3000` and the API at `http://localhost:8000`. Compose provisions database roles and applies migrations. Configure a site and staff access before embedding the widget.

## Development checks

Python 3.12+ and Node.js are required for development outside Docker.

```bash
cd backend
uv sync --group dev
uv run pytest
uv run ruff check .
```

```bash
cd frontend
npm ci
npm run typecheck
npm test
npm run build:loader
```

Environment examples contain placeholders. Configure your own hosts and credentials for deployment; deployment workflows require explicit configuration and enablement.
