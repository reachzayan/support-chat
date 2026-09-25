#!/bin/sh
set -eu

: "${MIGRATION_DATABASE_URL:?MIGRATION_DATABASE_URL is required}"
export DATABASE_URL="$MIGRATION_DATABASE_URL"
exec alembic upgrade head
