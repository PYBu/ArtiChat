#!/usr/bin/env bash
set -Eeuo pipefail

[[ "${EUID:-$(id -u)}" -eq 0 ]] || {
  echo 'this installer must run as root' >&2
  exit 2
}

DEPLOY_USER=''
PUBLIC_KEY_FILE=''
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

while (($#)); do
  case "$1" in
    --user)
      DEPLOY_USER="${2:-}"
      shift 2
      ;;
    --public-key-file)
      PUBLIC_KEY_FILE="${2:-}"
      shift 2
      ;;
    *)
      echo "unsupported argument: $1" >&2
      exit 2
      ;;
  esac
done

[[ "$DEPLOY_USER" =~ ^[A-Za-z_][A-Za-z0-9._-]{0,31}$ ]] || {
  echo 'invalid deployment user' >&2
  exit 2
}
id "$DEPLOY_USER" >/dev/null 2>&1 || {
  echo 'deployment user does not exist' >&2
  exit 2
}
[[ -r "$PUBLIC_KEY_FILE" ]] || {
  echo 'public key file is not readable' >&2
  exit 2
}

read -r key_type key_material _ < "$PUBLIC_KEY_FILE"
[[ "$key_type" == 'ssh-ed25519' && "$key_material" =~ ^[A-Za-z0-9+/]+={0,2}$ ]] || {
  echo 'public key must be an Ed25519 key' >&2
  exit 2
}
ssh-keygen -lf "$PUBLIC_KEY_FILE" | grep -q 'ED25519' || {
  echo 'public key must be a valid Ed25519 key' >&2
  exit 2
}

install -m 0755 "$SCRIPT_DIR/artichat-deploy.sh" /usr/local/sbin/artichat-deploy
install -m 0755 "$SCRIPT_DIR/artichat-deploy-ssh.sh" /usr/local/sbin/artichat-deploy-ssh

DEPLOY_GROUP="$(id -gn "$DEPLOY_USER")"
install -d -o "$DEPLOY_USER" -g "$DEPLOY_GROUP" -m 0750 \
  /data/artichat-prod /data/artichat-prod/data /data/artichat-prod/backups /data/artichat-prod/update-state

SUDOERS_FILE='/etc/sudoers.d/artichat-deploy'
SUDOERS_TEMPORARY="$(mktemp)"
trap 'rm -f "$SUDOERS_TEMPORARY"' EXIT
printf '%s ALL=(root) NOPASSWD: /usr/local/sbin/artichat-deploy\n' "$DEPLOY_USER" > "$SUDOERS_TEMPORARY"
chmod 0440 "$SUDOERS_TEMPORARY"
visudo -cf "$SUDOERS_TEMPORARY" >/dev/null
install -m 0440 "$SUDOERS_TEMPORARY" "$SUDOERS_FILE"

SSH_DIR="$(getent passwd "$DEPLOY_USER" | cut -d: -f6)/.ssh"
AUTHORIZED_KEYS="$SSH_DIR/authorized_keys"
[[ "$SSH_DIR" != '/.ssh' && ! -L "$SSH_DIR" && ! -L "$AUTHORIZED_KEYS" ]] || {
  echo 'unsafe SSH directory or authorized_keys path' >&2
  exit 2
}
install -d -o "$DEPLOY_USER" -g "$DEPLOY_GROUP" -m 0700 "$SSH_DIR"
touch "$AUTHORIZED_KEYS"
chown "$DEPLOY_USER:$DEPLOY_GROUP" "$AUTHORIZED_KEYS"
chmod 0600 "$AUTHORIZED_KEYS"

RESTRICTED_KEY="command=\"/usr/local/sbin/artichat-deploy-ssh\",no-agent-forwarding,no-port-forwarding,no-X11-forwarding,no-pty ssh-ed25519 $key_material artichat-github-actions"
AUTHORIZED_KEYS_TEMPORARY="$(mktemp)"
grep -Fv " $key_material " "$AUTHORIZED_KEYS" > "$AUTHORIZED_KEYS_TEMPORARY" || true
printf '%s\n' "$RESTRICTED_KEY" >> "$AUTHORIZED_KEYS_TEMPORARY"
install -o "$DEPLOY_USER" -g "$DEPLOY_GROUP" -m 0600 "$AUTHORIZED_KEYS_TEMPORARY" "$AUTHORIZED_KEYS"
rm -f "$AUTHORIZED_KEYS_TEMPORARY"

echo 'ArtiChat update runner installed.'
