#!/usr/bin/env bash
# Send pinned deploy script to EC2 via SSM and poll until completion.
#
# Required env:
#   INSTANCE_ID, DEPLOY_SHA, GITHUB_TOKEN, REPO_DIR, GITHUB_REPO, BRANCH
# Optional:
#   SSM_POLL_ITERATIONS (default 180), SSM_POLL_INTERVAL_SECONDS (default 10),
#   COMPOSE_FILE, COMPOSE_PROD_FILE, COMPOSE_APP_SERVICES, POSTGRES_VOLUME_FILTER,
#   AWS_REGION (passed through to aws cli if set)
set -euo pipefail

INSTANCE_ID="${INSTANCE_ID:?INSTANCE_ID required}"
DEPLOY_SHA="${DEPLOY_SHA:?DEPLOY_SHA required}"
GITHUB_TOKEN="${GITHUB_TOKEN:?GITHUB_TOKEN required}"
REPO_DIR="${REPO_DIR:?REPO_DIR required}"
GITHUB_REPO="${GITHUB_REPO:?GITHUB_REPO required}"
BRANCH="${BRANCH:?BRANCH required}"
SSM_POLL_ITERATIONS="${SSM_POLL_ITERATIONS:-180}"
SSM_POLL_INTERVAL_SECONDS="${SSM_POLL_INTERVAL_SECONDS:-10}"

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

{
  echo "export DEPLOY_SHA='${DEPLOY_SHA}'"
  echo "export BRANCH='${BRANCH}'"
  echo "export GITHUB_TOKEN='${GITHUB_TOKEN}'"
  echo "export REPO_DIR='${REPO_DIR}'"
  echo "export GITHUB_REPO='${GITHUB_REPO}'"
  echo "export COMPOSE_FILE='${COMPOSE_FILE:-docker-compose.yml}'"
  echo "export COMPOSE_PROD_FILE='${COMPOSE_PROD_FILE:-docker-compose.prod.yml}'"
  echo "export COMPOSE_APP_SERVICES='${COMPOSE_APP_SERVICES:-backend frontend}'"
  echo "export POSTGRES_VOLUME_FILTER='${POSTGRES_VOLUME_FILTER:-postgres_data}'"
  cat "${REPO_ROOT}/deploy/ssm-deploy.sh"
} > /tmp/ssm-deploy-pinned.sh

COMMANDS_JSON=$(bash "${REPO_ROOT}/deploy/ssm-commands-json.sh" /tmp/ssm-deploy-pinned.sh)

COMMAND_ID=$(aws ssm send-command \
  --instance-ids "$INSTANCE_ID" \
  --document-name "AWS-RunShellScript" \
  --comment "Deploy ${GITHUB_REPO} @ ${DEPLOY_SHA}" \
  --parameters "{\"commands\":${COMMANDS_JSON}}" \
  --query "Command.CommandId" --output text)

echo "SSM command: $COMMAND_ID"

STATUS="Pending"
for _ in $(seq 1 "$SSM_POLL_ITERATIONS"); do
  STATUS=$(aws ssm get-command-invocation \
    --command-id "$COMMAND_ID" \
    --instance-id "$INSTANCE_ID" \
    --query "Status" --output text 2>/dev/null || echo "Pending")

  case "$STATUS" in
    Success) break ;;
    Failed|Cancelled|TimedOut)
      echo "Deploy failed with status: $STATUS"
      aws ssm get-command-invocation \
        --command-id "$COMMAND_ID" \
        --instance-id "$INSTANCE_ID" \
        --query "StandardErrorContent" --output text
      exit 1
      ;;
    *) sleep "$SSM_POLL_INTERVAL_SECONDS" ;;
  esac
done

if [ "$STATUS" != "Success" ]; then
  echo "Timed out waiting for deploy command to finish (last status: $STATUS)"
  exit 1
fi

echo "Deploy succeeded."
aws ssm get-command-invocation \
  --command-id "$COMMAND_ID" \
  --instance-id "$INSTANCE_ID" \
  --query "StandardOutputContent" --output text
