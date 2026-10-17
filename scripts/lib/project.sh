#!/usr/bin/env bash

readonly EXIT_USAGE=2
readonly EXIT_NO_PROJECT=3
readonly EXIT_NO_TOOL=4

repo_root() {
  git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel
}

secrets_file() {
  echo "${BARA_ENV:-$(repo_root)/.secrets/bara.env}"
}

read_secret_value() {
  local key="$1" file value
  file="$(secrets_file)"
  [[ -f "$file" ]] || return 0
  value="$({ grep -E "^${key}=" "$file" || true; } | tail -1 | cut -d= -f2- | tr -d '\r')"
  value="${value#\"}"
  echo "${value%\"}"
}

resolve_project() {
  local flag_value="$1"
  if [[ -n "$flag_value" ]]; then echo "$flag_value"; return; fi
  if [[ -n "${PROJECT:-}" ]]; then echo "$PROJECT"; return; fi
  read_secret_value PROJECT
}

require_project() {
  local project="$1"
  if [[ -z "$project" ]]; then
    echo "no project set" >&2
    echo "pass --project <id>, set PROJECT, or put PROJECT=<id> in $(secrets_file)" >&2
    exit "$EXIT_NO_PROJECT"
  fi
}

require_tools() {
  local tool
  for tool in "$@"; do
    if ! command -v "$tool" >/dev/null 2>&1; then
      echo "$tool not found on PATH" >&2
      echo "install the Google Cloud CLI (gcloud, bq) and curl, then run again" >&2
      exit "$EXIT_NO_TOOL"
    fi
  done
}
