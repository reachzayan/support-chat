#!/usr/bin/env sh
# One-shot local stack: Postgres + Redis + API (migrate + seed + serve).
set -eu
cd "$(dirname "$0")/.."

if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created .env from .env.example (add ANTHROPIC_API_KEY / OPENAI_API_KEY when you need the bot)."
fi

docker compose up --build "$@"
