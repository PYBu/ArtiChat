#!/usr/bin/env bash
set -Eeuo pipefail

TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_SCRIPT="$TEST_DIR/../artichat-deploy.sh"
TMP_ROOT="$(mktemp -d)"
trap 'rm -rf "$TMP_ROOT"' EXIT

fail() {
  echo "test failed: $*" >&2
  exit 1
}

setup_case() {
  local case_name="$1"
  local mode="$2"
  local root="$TMP_ROOT/$case_name"

  mkdir -p "$root/deploy/data" "$root/deploy/backups" "$root/deploy/update-state" "$root/bin"
  printf 'original-user-data\n' > "$root/deploy/data/user-data.txt"
  printf 'WEBUI_SECRET_KEY=test-only\n' > "$root/deploy/.env"
  printf 'ARTICHAT_IMAGE=ghcr.io/artivis-test/artichat:0.1.1\n' > "$root/deploy/image.env"
  printf 'services:\n  artichat: {}\n' > "$root/deploy/docker-compose.yaml"

  cat > "$root/bin/python3" <<'EOF'
#!/usr/bin/env bash
exec python "$@"
EOF

  cat > "$root/bin/flock" <<'EOF'
#!/usr/bin/env bash
exit 0
EOF

  cat > "$root/bin/tar" <<'EOF'
#!/usr/bin/env bash
set -Eeuo pipefail
if [[ "${FAKE_TAR_FAIL_EXTRACT:-false}" == "true" && "$*" == *"-xzf"* ]]; then
  exit 1
fi
exec /usr/bin/tar "$@"
EOF

  cat > "$root/bin/docker" <<'EOF'
#!/usr/bin/env bash
set -Eeuo pipefail
printf '%s\n' "$*" >> "$FAKE_DOCKER_LOG"

if [[ "${1:-}" == "image" && "${2:-}" == "ls" ]]; then
  printf '%s\n' \
    'ghcr.io/artivis-test/artichat:0.1.2' \
    'ghcr.io/artivis-test/artichat:0.1.1' \
    'ghcr.io/artivis-test/artichat:0.1.0'
  exit 0
fi

if [[ "$*" == *" up -d --no-deps --force-recreate artichat"* ]]; then
  image="$(sed -n 's/^ARTICHAT_IMAGE=//p' "$ARTICHAT_IMAGE_ENV_FILE" | tail -n 1)"
  if [[ "$FAKE_CURL_MODE" == "failure" && "$image" == *":0.1.2" ]]; then
    printf 'failed-new-data\n' > "$ARTICHAT_DATA_DIR/user-data.txt"
  fi
fi
EOF

  cat > "$root/bin/curl" <<'EOF'
#!/usr/bin/env bash
set -Eeuo pipefail
url="${*: -1}"
if [[ "$url" == */health ]]; then
  printf '{"status":true}\n'
  exit 0
fi
if [[ "$url" == */api/version ]]; then
  image="$(sed -n 's/^ARTICHAT_IMAGE=//p' "$ARTICHAT_IMAGE_ENV_FILE" | tail -n 1)"
  version="${image##*:}"
  if [[ "$FAKE_CURL_MODE" == "failure" && "$version" == "0.1.2" ]]; then
    version='0.1.1'
  fi
  printf '{"version":"%s"}\n' "$version"
  exit 0
fi
exit 1
EOF

  chmod +x "$root/bin/python3" "$root/bin/flock" "$root/bin/tar" "$root/bin/docker" "$root/bin/curl"

  export PATH="$root/bin:$ORIGINAL_PATH"
  export ARTICHAT_DEPLOY_DIR="$root/deploy"
  export ARTICHAT_DATA_DIR="$root/deploy/data"
  export ARTICHAT_BACKUP_DIR="$root/deploy/backups"
  export ARTICHAT_UPDATE_STATE_FILE="$root/deploy/update-state/status.json"
  export ARTICHAT_IMAGE_REPOSITORY="ghcr.io/artivis-test/artichat"
  export ARTICHAT_COMPOSE_FILE="$root/deploy/docker-compose.yaml"
  export ARTICHAT_ENV_FILE="$root/deploy/.env"
  export ARTICHAT_IMAGE_ENV_FILE="$root/deploy/image.env"
  export ARTICHAT_HEALTH_URL="http://127.0.0.1:13000"
  export ARTICHAT_VERIFY_TIMEOUT_SECONDS=1
  export ARTICHAT_VERIFY_INTERVAL_SECONDS=0.1
  export FAKE_DOCKER_LOG="$root/docker.log"
  export FAKE_CURL_MODE="$mode"
  export FAKE_TAR_FAIL_EXTRACT=false
}

ORIGINAL_PATH="$PATH"

setup_case success success
"$DEPLOY_SCRIPT" 0.1.2 operation-success

grep -q 'ARTICHAT_IMAGE=ghcr.io/artivis-test/artichat:0.1.2' "$ARTICHAT_IMAGE_ENV_FILE" || fail 'target image was not persisted'
grep -q '"stage": "completed"' "$ARTICHAT_UPDATE_STATE_FILE" || fail 'success state was not completed'
test -f "$ARTICHAT_DATA_DIR/user-data.txt" || fail 'success removed user data'
test "$(find "$ARTICHAT_BACKUP_DIR" -type f | wc -l)" -eq 1 || fail 'success backup count was not one'
grep -q '^pull ghcr.io/artivis-test/artichat:0.1.2$' "$FAKE_DOCKER_LOG" || fail 'target image was not pulled first'
grep -q ' stop artichat$' "$FAKE_DOCKER_LOG" || fail 'artichat service was not stopped explicitly'
grep -q ' up -d --no-deps --force-recreate artichat$' "$FAKE_DOCKER_LOG" || fail 'artichat service was not recreated in isolation'
if grep -Eq '(^| )down( |$)|--volumes|system prune' "$FAKE_DOCKER_LOG"; then
  fail 'unsafe Docker command was used'
fi

setup_case failure failure
if "$DEPLOY_SCRIPT" 0.1.2 operation-failure; then
  fail 'version mismatch deployment unexpectedly succeeded'
fi

grep -q 'ARTICHAT_IMAGE=ghcr.io/artivis-test/artichat:0.1.1' "$ARTICHAT_IMAGE_ENV_FILE" || fail 'rollback did not restore previous image'
grep -q '^original-user-data$' "$ARTICHAT_DATA_DIR/user-data.txt" || fail 'rollback did not restore original data'
grep -q '"stage": "rolled_back"' "$ARTICHAT_UPDATE_STATE_FILE" || fail 'rollback state was not recorded'

setup_case rollback-failure failure
export FAKE_TAR_FAIL_EXTRACT=true
if "$DEPLOY_SCRIPT" 0.1.2 operation-rollback-failure; then
  fail 'rollback extraction failure unexpectedly succeeded'
fi

grep -q '"stage": "failed"' "$ARTICHAT_UPDATE_STATE_FILE" || fail 'failed rollback was reported as successful'
test "$(find "$ARTICHAT_BACKUP_DIR" -type f | wc -l)" -eq 1 || fail 'failed rollback did not preserve its backup'

echo 'artichat deploy tests passed'
