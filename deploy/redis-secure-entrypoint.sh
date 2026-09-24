#!/bin/sh
set -eu

: "${REDIS_APP_PASSWORD:?REDIS_APP_PASSWORD is required}"
: "${REDIS_ADMIN_PASSWORD:?REDIS_ADMIN_PASSWORD is required}"

app_hash="$(printf '%s' "$REDIS_APP_PASSWORD" | sha256sum | cut -d ' ' -f 1)"
admin_hash="$(printf '%s' "$REDIS_ADMIN_PASSWORD" | sha256sum | cut -d ' ' -f 1)"

umask 077
mkdir -p /run/redis
{
  printf 'user default off\n'
  printf 'user app on #%s ~rate:* ~ratekey:* ~kb:* ~bot:* ~worker:* &chat:wakeup +ping +auth +hello +select +client +get +set +del +incr +decr +expire +ttl +eval +rpush +blpop +publish +subscribe +unsubscribe +psubscribe +punsubscribe\n' "$app_hash"
  printf 'user admin on #%s ~* &* +@all\n' "$admin_hash"
} > /run/redis/users.acl

exec redis-server \
  --port 0 \
  --tls-port 6379 \
  --tls-cert-file /run/tls/redis.crt \
  --tls-key-file /run/tls/redis.key \
  --tls-ca-cert-file /run/tls/ca.crt \
  --tls-auth-clients no \
  --aclfile /run/redis/users.acl \
  --appendonly yes
