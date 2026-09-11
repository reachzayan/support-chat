# EC2 one-time bootstrap (run on ai-webchat-dev after cloning the repo).
# All values come from environment / prompts — nothing sensitive is committed.
#
# Prerequisites on the instance (same as inbox-triage):
#   - Docker Engine + Compose plugin, enabled
#   - nginx + certbot
#   - Elastic IP associated (sslip.io hostname encodes it)
#
# Usage (as ssm-user, with sudo where noted):
#   export PUBLIC_HOST=deployment.example.com
#   export REPO_DIR=/home/ssm-user/support-chat
#   bash deploy/bootstrap-ec2.sh

set -euo pipefail

REPO_DIR="${REPO_DIR:?REPO_DIR required}"
PUBLIC_HOST="${PUBLIC_HOST:?PUBLIC_HOST required (e.g. deployment.example.com)}"
NGINX_CONF_DEST="${NGINX_CONF_DEST:-/etc/nginx/conf.d/ai-webchat.conf}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.yml}"
COMPOSE_PROD_FILE="${COMPOSE_PROD_FILE:-docker-compose.prod.yml}"

cd "$REPO_DIR"

if [ ! -f .env ]; then
  echo "Missing $REPO_DIR/.env — copy .env.example and fill secrets first." >&2
  exit 1
fi
if [ ! -f backend/.env.prod ]; then
  echo "Missing $REPO_DIR/backend/.env.prod — copy backend/.env.prod.example and fill secrets first." >&2
  exit 1
fi

# shellcheck disable=SC1091
set -a
# shellcheck disable=SC1091
source .env
set +a

sed "s/__PUBLIC_HOST__/${PUBLIC_HOST}/g" deploy/nginx.conf.template \
  | sudo tee "$NGINX_CONF_DEST" > /dev/null
sudo nginx -t
sudo systemctl reload nginx

docker compose -f "$COMPOSE_FILE" -f "$COMPOSE_PROD_FILE" up --build -d

echo "Stack started. Issue TLS with:"
echo "  sudo certbot --nginx -d ${PUBLIC_HOST}"
echo "Then set COOKIE_SECURE=true and https:// origins in backend/.env.prod + root .env, rebuild frontend."
