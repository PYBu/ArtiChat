#!/usr/bin/env bash
set -Eeuo pipefail

TARGET_VERSION="${1:-}"
OPERATION_ID="${2:-}"
[[ "$TARGET_VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || {
  echo 'invalid version' >&2
  exit 2
}
[[ "$OPERATION_ID" =~ ^[A-Za-z0-9._-]{8,128}$ ]] || {
  echo 'invalid operation id' >&2
  exit 2
}

DEPLOY_DIR="${ARTICHAT_DEPLOY_DIR:-/data/artichat-prod}"
DATA_DIR="${ARTICHAT_DATA_DIR:-$DEPLOY_DIR/data}"
BACKUP_DIR="${ARTICHAT_BACKUP_DIR:-$DEPLOY_DIR/backups}"
STATE_FILE="${ARTICHAT_UPDATE_STATE_FILE:-$DEPLOY_DIR/update-state/status.json}"
COMPOSE_FILE="${ARTICHAT_COMPOSE_FILE:-$DEPLOY_DIR/docker-compose.yaml}"
ENV_FILE="${ARTICHAT_ENV_FILE:-$DEPLOY_DIR/.env}"
IMAGE_ENV_FILE="${ARTICHAT_IMAGE_ENV_FILE:-$DEPLOY_DIR/image.env}"
IMAGE_REPOSITORY="${ARTICHAT_IMAGE_REPOSITORY:?ARTICHAT_IMAGE_REPOSITORY is required}"
HEALTH_URL="${ARTICHAT_HEALTH_URL:-http://127.0.0.1:13000}"
VERIFY_TIMEOUT_SECONDS="${ARTICHAT_VERIFY_TIMEOUT_SECONDS:-180}"
VERIFY_INTERVAL_SECONDS="${ARTICHAT_VERIFY_INTERVAL_SECONDS:-2}"

[[ "$VERIFY_TIMEOUT_SECONDS" =~ ^[0-9]+$ ]] || {
  echo 'invalid verify timeout' >&2
  exit 2
}
[[ "$VERIFY_INTERVAL_SECONDS" =~ ^[0-9]+([.][0-9]+)?$ ]] || {
  echo 'invalid verify interval' >&2
  exit 2
}
[[ "$IMAGE_REPOSITORY" =~ ^ghcr[.]io/[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$ ]] || {
  echo 'invalid ARTICHAT_IMAGE_REPOSITORY' >&2
  exit 2
}

resolve_path() {
  python3 - "$1" <<'PY'
import os
import sys

print(os.path.realpath(sys.argv[1]).replace(os.sep, '/'))
PY
}

require_under_deploy() {
  local name="$1"
  local candidate="$2"
  [[ -n "$candidate" && "$candidate" != '/' ]] || {
    echo "$name must not be empty or root" >&2
    exit 2
  }
  case "$candidate" in
    "$DEPLOY_DIR"/*) ;;
    *)
      echo "$name must stay under $DEPLOY_DIR" >&2
      exit 2
      ;;
  esac
}

if [[ -z "$DEPLOY_DIR" || "$DEPLOY_DIR" == '/' ]]; then
  echo 'ARTICHAT_DEPLOY_DIR must not be empty or root' >&2
  exit 2
fi

mkdir -p "$DEPLOY_DIR"
DEPLOY_DIR="$(resolve_path "$DEPLOY_DIR")"
DATA_DIR="$(resolve_path "$DATA_DIR")"
BACKUP_DIR="$(resolve_path "$BACKUP_DIR")"
STATE_FILE="$(resolve_path "$STATE_FILE")"
COMPOSE_FILE="$(resolve_path "$COMPOSE_FILE")"
ENV_FILE="$(resolve_path "$ENV_FILE")"
IMAGE_ENV_FILE="$(resolve_path "$IMAGE_ENV_FILE")"

require_under_deploy 'ARTICHAT_DATA_DIR' "$DATA_DIR"
require_under_deploy 'ARTICHAT_BACKUP_DIR' "$BACKUP_DIR"
require_under_deploy 'ARTICHAT_UPDATE_STATE_FILE' "$STATE_FILE"
require_under_deploy 'ARTICHAT_COMPOSE_FILE' "$COMPOSE_FILE"
require_under_deploy 'ARTICHAT_ENV_FILE' "$ENV_FILE"
require_under_deploy 'ARTICHAT_IMAGE_ENV_FILE' "$IMAGE_ENV_FILE"

LOCK_FILE="$DEPLOY_DIR/update.lock"
mkdir -p "$BACKUP_DIR" "$(dirname "$STATE_FILE")"
exec 9>"$LOCK_FILE"
flock -n 9 || {
  echo 'another deployment is running' >&2
  exit 3
}

TARGET_IMAGE="$IMAGE_REPOSITORY:$TARGET_VERSION"
SERVICE_STOPPED=false
BACKUP_READY=false
BACKUP_FILE=''
BACKUP_TEMPORARY=''
OLD_IMAGE=''
OLD_VERSION=''

write_state() {
  local stage="$1"
  local active="$2"
  local message="$3"
  local error="${4:-}"
  python3 - "$STATE_FILE" "$OPERATION_ID" "$TARGET_VERSION" "$OLD_VERSION" "$stage" "$active" "$message" "$error" <<'PY'
import json
import os
import sys
import time
from pathlib import Path

path = Path(sys.argv[1])
state = {
    'operation_id': sys.argv[2],
    'target_version': sys.argv[3],
    'previous_version': sys.argv[4] or None,
    'stage': sys.argv[5],
    'active': sys.argv[6].lower() == 'true',
    'message': sys.argv[7],
    'error': sys.argv[8] or None,
    'updated_at': int(time.time()),
}
path.parent.mkdir(parents=True, exist_ok=True)
temporary = path.with_name(f'{path.name}.{os.getpid()}.tmp')
try:
    temporary.write_text(json.dumps(state, ensure_ascii=False), encoding='utf-8')
    os.replace(temporary, path)
finally:
    temporary.unlink(missing_ok=True)
PY
}

compose() {
  docker compose --env-file "$ENV_FILE" --env-file "$IMAGE_ENV_FILE" -f "$COMPOSE_FILE" "$@"
}

read_image() {
  sed -n 's/^ARTICHAT_IMAGE=//p' "$IMAGE_ENV_FILE" | tail -n 1
}

write_image() {
  local image="$1"
  local temporary="${IMAGE_ENV_FILE}.$$"
  if ! printf 'ARTICHAT_IMAGE=%s\n' "$image" > "$temporary"; then
    rm -f -- "$temporary"
    return 1
  fi
  if ! mv -f "$temporary" "$IMAGE_ENV_FILE"; then
    rm -f -- "$temporary"
    return 1
  fi
}

read_version() {
  local payload
  payload="$(curl -fsS "$HEALTH_URL/api/version")"
  python3 - "$payload" <<'PY'
import json
import re
import sys

version = json.loads(sys.argv[1]).get('version', '')
if not isinstance(version, str) or not re.fullmatch(r'\d+\.\d+\.\d+', version):
    raise SystemExit(1)
print(version)
PY
}

verify_health() {
  local payload
  payload="$(curl -fsS "$HEALTH_URL/health")" || return 1
  python3 - "$payload" <<'PY'
import json
import sys

if json.loads(sys.argv[1]).get('status') is not True:
    raise SystemExit(1)
PY
}

verify_release() {
  local expected="$1"
  local deadline=$((SECONDS + VERIFY_TIMEOUT_SECONDS))
  local actual
  while (( SECONDS <= deadline )); do
    if verify_health && actual="$(read_version)" && [[ "$actual" == "$expected" ]]; then
      return 0
    fi
    sleep "$VERIFY_INTERVAL_SECONDS"
  done
  return 1
}

preflight_disk() {
  [[ -d "$DATA_DIR" ]] || {
    echo 'data directory does not exist' >&2
    return 1
  }
  local data_bytes available_bytes required_bytes
  data_bytes="$(du -sb "$DATA_DIR" | awk '{print $1}')"
  available_bytes="$(df -PB1 "$DEPLOY_DIR" | awk 'NR == 2 {print $4}')"
  required_bytes=$((data_bytes * 2 + 1073741824))
  (( available_bytes >= required_bytes )) || {
    echo 'insufficient disk space for backup and rollback' >&2
    return 1
  }
}

rotate_backups() {
  local -a backups=()
  mapfile -t backups < <(find "$BACKUP_DIR" -maxdepth 1 -type f -name 'artichat-data-*.tar.gz' -printf '%T@ %p\n' | sort -nr)
  local index path
  for (( index = 3; index < ${#backups[@]}; index++ )); do
    path="${backups[$index]#* }"
    rm -f -- "$path"
  done
}

prune_old_images() {
  local -a images=()
  mapfile -t images < <(docker image ls "$IMAGE_REPOSITORY" --format '{{.Repository}}:{{.Tag}}' || true)
  local image
  for image in "${images[@]}"; do
    [[ "$image" == "$TARGET_IMAGE" || "$image" == "$OLD_IMAGE" ]] || docker image rm "$image" || true
  done
}

rollback() {
  local exit_code="$1"
  trap - ERR
  set +e

  local rollback_data
  rollback_data="$(resolve_path "$DEPLOY_DIR/.artichat-rollback-data-$OPERATION_ID")"
  require_under_deploy 'rollback data directory' "$rollback_data"

  rollback_failed() {
    local error="$1"
    write_state 'failed' false 'Deployment and rollback failed' "$error" || true
    exit 1
  }

  if [[ "$SERVICE_STOPPED" == true ]]; then
    compose stop artichat >/dev/null 2>&1 || rollback_failed 'Unable to stop the failed deployment'
    rm -rf -- "$rollback_data" || rollback_failed 'Unable to prepare rollback staging directory'
    mv -- "$DATA_DIR" "$rollback_data" || rollback_failed 'Unable to isolate failed deployment data'
    mkdir -p "$DATA_DIR" || rollback_failed 'Unable to recreate the data directory'
    tar --force-local -xzf "$BACKUP_FILE" -C "$DATA_DIR" || rollback_failed 'Unable to restore the deployment backup'
    write_image "$OLD_IMAGE" || rollback_failed 'Unable to restore the previous image configuration'
    compose up -d --no-deps --force-recreate artichat >/dev/null 2>&1 || rollback_failed 'Unable to restart the previous image'
    verify_release "$OLD_VERSION" || rollback_failed 'Rollback health verification failed'
    write_state 'rolled_back' false 'Deployment failed and was rolled back' 'Deployment verification failed' || exit_code=1
    rm -rf -- "$rollback_data" || true
  else
    write_state 'failed' false 'Deployment failed' 'Deployment failed before service stop'
  fi
  exit "$exit_code"
}

handle_error() {
  local exit_code="$?"
  trap - ERR
  if [[ "$BACKUP_READY" == true ]]; then
    rollback "$exit_code"
  else
    set +e
    [[ -z "$BACKUP_TEMPORARY" ]] || rm -f -- "$BACKUP_TEMPORARY"
    if [[ "$SERVICE_STOPPED" == true ]]; then
      compose up -d --no-deps --force-recreate artichat >/dev/null 2>&1
    fi
    write_state 'failed' false 'Deployment failed' 'Deployment failed before backup was ready'
    exit "$exit_code"
  fi
}

trap handle_error ERR

write_state 'preparing' true 'Preparing deployment'
preflight_disk

OLD_IMAGE="$(read_image)"
[[ -n "$OLD_IMAGE" ]] || {
  echo 'ARTICHAT_IMAGE is missing from image.env' >&2
  exit 1
}
OLD_VERSION="$(read_version)"

write_state 'pulling' true 'Pulling target image'
docker pull "$TARGET_IMAGE"

compose stop artichat
SERVICE_STOPPED=true

write_state 'backing_up' true 'Backing up data'
timestamp="$(date +%Y%m%d-%H%M%S)"
BACKUP_FILE="$BACKUP_DIR/artichat-data-$timestamp-$OPERATION_ID.tar.gz"
BACKUP_TEMPORARY="$BACKUP_FILE.tmp"
tar --force-local -C "$DATA_DIR" -czf "$BACKUP_TEMPORARY" .
mv -f "$BACKUP_TEMPORARY" "$BACKUP_FILE"
BACKUP_TEMPORARY=''
BACKUP_READY=true

write_image "$TARGET_IMAGE"
write_state 'restarting' true 'Restarting ArtiChat'
compose up -d --no-deps --force-recreate artichat

write_state 'verifying' true 'Verifying health and version'
verify_release "$TARGET_VERSION"

write_state 'completed' false 'Deployment completed'
trap - ERR
rotate_backups || true
prune_old_images || true
