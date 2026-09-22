#!/bin/sh
set -eu

TLS_DIR="${REDIS_TLS_DIR:-./deploy/redis-tls}"

if [ -f "$TLS_DIR/ca.crt" ] && [ -f "$TLS_DIR/redis.crt" ] && [ -f "$TLS_DIR/redis.key" ]; then
  echo "Redis TLS material already exists in $TLS_DIR"
  exit 0
fi

if [ -e "$TLS_DIR/ca.crt" ] || [ -e "$TLS_DIR/redis.crt" ] || [ -e "$TLS_DIR/redis.key" ]; then
  echo "Redis TLS material is incomplete in $TLS_DIR; inspect it before retrying." >&2
  exit 1
fi

umask 077
mkdir -p "$TLS_DIR"

openssl req -x509 -newkey rsa:3072 -sha256 -nodes \
  -keyout "$TLS_DIR/ca.key" \
  -out "$TLS_DIR/ca.crt" \
  -days 3650 \
  -subj "/CN=SupportChat Redis CA"

openssl req -new -newkey rsa:3072 -sha256 -nodes \
  -keyout "$TLS_DIR/redis.key" \
  -out "$TLS_DIR/redis.csr" \
  -subj "/CN=redis" \
  -addext "subjectAltName=DNS:redis"

openssl x509 -req -sha256 \
  -in "$TLS_DIR/redis.csr" \
  -CA "$TLS_DIR/ca.crt" \
  -CAkey "$TLS_DIR/ca.key" \
  -CAcreateserial \
  -copy_extensions copy \
  -out "$TLS_DIR/redis.crt" \
  -days 825

# The directory is mode 700 from umask, so only the deployment owner can read
# the key on the host. The read-only bind exposes it only inside the Redis container.
chmod 700 "$TLS_DIR"
chmod 644 "$TLS_DIR/ca.crt" "$TLS_DIR/redis.crt" "$TLS_DIR/redis.key"
echo "Generated Redis TLS material in $TLS_DIR"
