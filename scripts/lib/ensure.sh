#!/usr/bin/env bash

report() {
  local state="$1" kind="$2" name="$3"
  printf '%-10s %-16s %s\n' "$state" "$kind" "$name"
}

ensure() {
  local kind="$1" name="$2" check_fn="$3" create_fn="$4"
  if "$check_fn" "$name"; then
    report ok "$kind" "$name"
    return
  fi
  if [[ "$DRY_RUN" == true ]]; then
    report "would make" "$kind" "$name"
    return
  fi
  "$create_fn" "$name"
  report made "$kind" "$name"
}
