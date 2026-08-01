#!/usr/bin/env bash
set -Eeuo pipefail

[[ "${SSH_ORIGINAL_COMMAND:-}" != *$'\n'* ]] || {
  echo 'unsupported command' >&2
  exit 2
}
read -r action version operation_id extra <<<"${SSH_ORIGINAL_COMMAND:-}"
[[ "$action" == 'deploy' && -z "${extra:-}" ]] || {
  echo 'unsupported command' >&2
  exit 2
}
[[ "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || {
  echo 'invalid version' >&2
  exit 2
}
[[ "$operation_id" =~ ^[A-Za-z0-9._-]{8,128}$ ]] || {
  echo 'invalid operation id' >&2
  exit 2
}

exec sudo /usr/local/sbin/artichat-deploy "$version" "$operation_id"
