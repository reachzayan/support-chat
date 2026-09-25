#!/usr/bin/env bash
# Runs on the EC2 instance via `aws ssm send-command` (AWS-RunShellScript).
# SSM executes as root — use safe.directory instead of git config --global.
#
# Required env (exported by the workflow / github-actions-ssm-deploy.sh):
#   DEPLOY_SHA, REPO_DIR, GITHUB_REPO, BRANCH
# The instance must have a read-only GitHub deploy key and pinned github.com host key.
# Optional:
#   COMPOSE_FILE, COMPOSE_PROD_FILE, COMPOSE_APP_SERVICES, POSTGRES_VOLUME_FILTER
set -euo pipefail

REPO_DIR="${REPO_DIR:?REPO_DIR required}"
GITHUB_REPO="${GITHUB_REPO:?GITHUB_REPO required}"
BRANCH="${BRANCH:?BRANCH required}"
SHA="${DEPLOY_SHA:?DEPLOY_SHA required}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.yml}"
COMPOSE_PROD_FILE="${COMPOSE_PROD_FILE:-docker-compose.prod.yml}"
COMPOSE_APP_SERVICES="${COMPOSE_APP_SERVICES:-backend worker frontend}"
POSTGRES_VOLUME_FILTER="${POSTGRES_VOLUME_FILTER:-postgres_data}"
REPO_URL="${REPO_URL:-git@github.com:${GITHUB_REPO}.git}"
export GIT_SSH_COMMAND="ssh -o BatchMode=yes -o StrictHostKeyChecking=yes"

# First deploy uses the instance's read-only deploy key; no credential is sent via SSM.
if [ ! -d "${REPO_DIR}/.git" ]; then
  if [ -e "${REPO_DIR}" ]; then
    echo "REPO_DIR exists without .git — refusing to overwrite: ${REPO_DIR}" >&2
    exit 1
  fi
  echo "REPO_DIR missing — cloning ${GITHUB_REPO} (${BRANCH}) into ${REPO_DIR}"
  mkdir -p "$(dirname "${REPO_DIR}")"
  git -c "safe.directory=${REPO_DIR}" clone --branch "${BRANCH}" "${REPO_URL}" "${REPO_DIR}"
fi

GIT=(git -c "safe.directory=${REPO_DIR}")
cd "$REPO_DIR"

"${GIT[@]}" remote set-url origin "$REPO_URL"
"${GIT[@]}" fetch origin "+refs/heads/${BRANCH}:refs/remotes/origin/${BRANCH}"
if ! "${GIT[@]}" merge-base --is-ancestor "$SHA" "origin/$BRANCH"; then
  echo "DEPLOY_SHA $SHA is not an ancestor of origin/$BRANCH" >&2
  exit 1
fi
"${GIT[@]}" checkout --detach "$SHA"

COMPOSE=(docker compose -f "$COMPOSE_FILE" -f "$COMPOSE_PROD_FILE")

# Data safety: never wipe Postgres/Redis. Rebuild app containers only.
if ! docker volume ls -q --filter "name=${POSTGRES_VOLUME_FILTER}" | grep -q .; then
  echo "${POSTGRES_VOLUME_FILTER} volume not found — aborting (refusing fresh database)" >&2
  exit 1
fi

read -r -a APP_SERVICES <<< "$COMPOSE_APP_SERVICES"
"${COMPOSE[@]}" up --build -d --wait --wait-timeout 180 "${APP_SERVICES[@]}"
docker image prune -f
