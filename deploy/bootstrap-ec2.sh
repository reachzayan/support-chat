# EC2 one-time bootstrap (run on ai-webchat-dev after cloning the repo).
# All values come from environment / prompts — nothing sensitive is committed.
#
# Prerequisites on the instance (same as inbox-triage):
#   - Docker Engine + Compose plugin, enabled
#   - nginx + certbot
#   - Elastic IP associated (sslip.io hostname encodes it)
#
# Usage (as ssm-user, with sudo where noted):
#   export STAFF_HOST=deployment.example.com
#   export MARKETING_HOST=marketing.deployment.example.com
#   export WIDGET_HOST=widget.deployment.example.com
#   export LETSENCRYPT_EMAIL=ops@example.com
#   export REPO_DIR=/home/ssm-user/support-chat
#   bash deploy/bootstrap-ec2.sh

set -euo pipefail

REPO_DIR="${REPO_DIR:?REPO_DIR required}"
MARKETING_HOST="${MARKETING_HOST:?MARKETING_HOST required}"
STAFF_HOST="${STAFF_HOST:?STAFF_HOST required}"
WIDGET_HOST="${WIDGET_HOST:?WIDGET_HOST required}"
LETSENCRYPT_EMAIL="${LETSENCRYPT_EMAIL:?LETSENCRYPT_EMAIL required}"
NGINX_CONF_DEST="${NGINX_CONF_DEST:-/etc/nginx/conf.d/ai-webchat.conf}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.yml}"
COMPOSE_PROD_FILE="${COMPOSE_PROD_FILE:-docker-compose.prod.yml}"

cd "$REPO_DIR"

env_value() {
  sed -n "s/^$2=//p" "$1" | tail -n 1
}

require_env_value() {
  ACTUAL_VALUE="$(env_value "$1" "$2")"
  if [ "$ACTUAL_VALUE" != "$3" ]; then
    echo "$1 must set $2=$3" >&2
    exit 1
  fi
}

if [ ! -f .env ]; then
  echo "Missing $REPO_DIR/.env — copy .env.example and fill secrets first." >&2
  exit 1
fi
if [ ! -f backend/.env.prod ]; then
  echo "Missing $REPO_DIR/backend/.env.prod — copy backend/.env.prod.example and fill secrets first." >&2
  exit 1
fi

if [ "$MARKETING_HOST" = "$STAFF_HOST" ] || [ "$MARKETING_HOST" = "$WIDGET_HOST" ] || [ "$STAFF_HOST" = "$WIDGET_HOST" ]; then
  echo "MARKETING_HOST, STAFF_HOST, and WIDGET_HOST must be distinct." >&2
  exit 1
fi

require_env_value .env APP_ENV production
require_env_value backend/.env.prod APP_ENV production
require_env_value backend/.env.prod COOKIE_SECURE true
require_env_value backend/.env.prod STAFF_APP_ORIGIN "https://${STAFF_HOST}"
require_env_value backend/.env.prod WIDGET_ORIGIN "https://${WIDGET_HOST}"
require_env_value backend/.env.prod MARKETING_HOST_ORIGIN "https://${MARKETING_HOST}"
require_env_value .env NEXT_PUBLIC_STAFF_APP_ORIGIN "https://${STAFF_HOST}"
require_env_value .env NEXT_PUBLIC_WIDGET_ORIGIN "https://${WIDGET_HOST}"
require_env_value .env NEXT_PUBLIC_MARKETING_HOST_ORIGIN "https://${MARKETING_HOST}"

REDIS_TLS_DIR="${REDIS_TLS_DIR:-./deploy/redis-tls}" deploy/generate-redis-tls.sh

sed \
  -e "s/__MARKETING_HOST__/${MARKETING_HOST}/g" \
  -e "s/__STAFF_HOST__/${STAFF_HOST}/g" \
  -e "s/__WIDGET_HOST__/${WIDGET_HOST}/g" \
  deploy/nginx.conf.template \
  | sudo tee "$NGINX_CONF_DEST" > /dev/null
sudo nginx -t
sudo systemctl reload nginx

sudo certbot --nginx --non-interactive --agree-tos --redirect \
  --email "$LETSENCRYPT_EMAIL" \
  -d "$MARKETING_HOST" \
  -d "$STAFF_HOST" \
  -d "$WIDGET_HOST"

docker compose -f "$COMPOSE_FILE" -f "$COMPOSE_PROD_FILE" config > /dev/null
docker compose -f "$COMPOSE_FILE" -f "$COMPOSE_PROD_FILE" up --build -d

echo "Production stack started with isolated origins:"
echo "  marketing: https://${MARKETING_HOST}"
echo "  staff:     https://${STAFF_HOST}"
echo "  widget:    https://${WIDGET_HOST}"
