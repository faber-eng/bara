#!/usr/bin/env bash
set -euo pipefail

kind=${1:-}
name=${2:-}
region=${3:-}
project=${4:-}
if [ -z "$kind" ] || [ -z "$name" ] || [ -z "$region" ] || [ -z "$project" ]; then
  echo "usage: guard.sh services|jobs NAME REGION PROJECT" >&2
  exit 2
fi

dir=${GUARD_DIR:-/workspace}
started=$(cat "$dir/build-started")

live=$(gcloud run "$kind" list --region="$region" --project="$project" \
  --filter="metadata.name=$name" --format='value(metadata.labels.build_started)')

if [ -n "$live" ] && [ "$live" -gt "$started" ]; then
  echo "SUPERSEDED: $name was last deployed by a build that started later ($live > $started); skipping this deploy"
  touch "$dir/superseded-$name"
  exit 0
fi
echo "guard ok: $name is not newer than this build (live=${live:-none} this=$started)"
