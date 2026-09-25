#!/bin/sh
set -eu

echo "Waiting for Postgres..."
i=0
while [ "$i" -lt 60 ]; do
  if python -c "
from sqlalchemy import create_engine, text
from app.settings import get_settings
engine = create_engine(get_settings().sync_database_url, pool_pre_ping=True)
with engine.connect() as conn:
    conn.execute(text('SELECT 1'))
" 2>/dev/null; then
    break
  fi
  i=$((i + 1))
  sleep 1
done
if [ "$i" -eq 60 ]; then
  echo "Postgres did not become ready in time" >&2
  exit 1
fi

# Alembic migrations do not use Redis. Skip the wait when this container is
# only applying schema (prod Redis is TLS-only; a missing CA must not block migrate).
case " $* " in
  *" migrate.sh "*|*" alembic "*) ;;
  *)
    echo "Waiting for Redis..."
    i=0
    while [ "$i" -lt 60 ]; do
      if python -c "
import redis
from app.settings import get_settings
client = redis.Redis.from_url(get_settings().redis_url, socket_connect_timeout=1)
client.ping()
" 2>/dev/null; then
        break
      fi
      i=$((i + 1))
      sleep 1
    done
    if [ "$i" -eq 60 ]; then
      echo "Redis did not become ready in time" >&2
      exit 1
    fi
    ;;
esac

exec "$@"
