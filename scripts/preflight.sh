#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/lib/project.sh"

readonly ALL_CHECKS=(P1 P2 P3 P4)
readonly MIN_POSITIVES=300
readonly MIN_PHOTOS=40
readonly MAX_PHOTOS=60
readonly MIN_VOICE=10

PROJECT_FLAG=""
CHECKS=()
FAILED=0

usage() {
  cat <<'EOF'
Usage: scripts/preflight.sh [--project <id>] [P1] [P2] [P3] [P4]

Checks the facts the build plan rests on (requirements.md §15.1). With no check
names it runs all four.

  P1  Earth Engine is registered for the project
  P2  each Gemini model ID in config/models.yaml answers on Vertex (global)
  P3  bara.reignition_training has at least 300 positives in the train split
  P4  the eval set: 40 to 60 photos, 10+ voice notes, every labels.csv path exists

  --project <id>  project to check (default: $PROJECT, then .secrets/bara.env)
  -h, --help      show this help

FAST_MODEL and REASONING_MODEL override the IDs in config/models.yaml.
Prints one line per check: "PASS Pn <detail>" or "FAIL Pn <detail>".
Exit codes: 0 all passed, 1 a check failed, 2 usage error, 3 no project, 4 tool missing.
EOF
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --project)
        require_flag_value "$1" "$#"
        PROJECT_FLAG="$2"; shift 2 ;;
      -h|--help) usage; exit 0 ;;
      P1|P2|P3|P4) CHECKS+=("$1"); shift ;;
      *) echo "unknown argument: $1" >&2; usage >&2; exit "$EXIT_USAGE" ;;
    esac
  done
  if [[ ${#CHECKS[@]} -eq 0 ]]; then CHECKS=("${ALL_CHECKS[@]}"); fi
}

pass() {
  echo "PASS $1 $2"
}

fail() {
  echo "FAIL $1 $2"
  FAILED=1
}

token() {
  gcloud auth print-access-token
}

model_field() {
  local tier="$1" field="$2"
  awk -v tier="$tier:" -v field="$field:" '
    $1 == tier { inside = 1; next }
    /^[^ #]/ { inside = 0 }
    inside && $1 == field { print $2; exit }
  ' "$(repo_root)/config/models.yaml"
}

http_status() {
  curl -s --max-time 30 -o /dev/null -w '%{http_code}' "$@" || true
}

check_p1() {
  local code
  code="$(http_status -H "Authorization: Bearer $(token)" -H "x-goog-user-project: $PROJECT" \
    "https://earthengine.googleapis.com/v1/projects/$PROJECT/algorithms")"
  if [[ "$code" == 200 ]]; then
    pass P1 "Earth Engine answers for $PROJECT"
    return
  fi
  fail P1 "Earth Engine returned $code; register the project at https://code.earthengine.google.com/register and enable earthengine.googleapis.com"
}

generate_status() {
  local model="$1"
  http_status -X POST -H "Authorization: Bearer $(token)" -H 'Content-Type: application/json' \
    -d '{"contents":[{"role":"user","parts":[{"text":"ping"}]}]}' \
    "https://aiplatform.googleapis.com/v1/projects/$PROJECT/locations/global/publishers/google/models/$model:generateContent"
}

check_model() {
  local tier="$1" model="$2" fallback="$3" code fallback_code
  if [[ -z "$model" ]]; then
    fail P2 "no $tier model in config/models.yaml"
    return
  fi
  code="$(generate_status "$model")"
  if [[ "$code" == 200 ]]; then
    pass P2 "$tier $model answers"
    return
  fi
  if [[ -z "$fallback" ]]; then
    fail P2 "$tier $model returned $code and config/models.yaml has no fallback"
    return
  fi
  fallback_code="$(generate_status "$fallback")"
  fail P2 "$tier $model returned $code (fallback $fallback returned $fallback_code); if the fallback is 200, set it in config/models.yaml and log it in docs/DECISIONS.md"
}

check_p2() {
  check_model fast "${FAST_MODEL:-$(model_field fast model)}" "$(model_field fast fallback)"
  check_model reasoning "${REASONING_MODEL:-$(model_field reasoning model)}" "$(model_field reasoning fallback)"
}

check_p3() {
  local positives
  if ! positives="$(bq --project_id "$PROJECT" query --quiet --use_legacy_sql=false --format=csv \
    "SELECT COUNTIF(reignited = 1) AS positives FROM bara.reignition_training WHERE split = 'train'" 2>&1 | tail -1)"; then
    fail P3 "query on bara.reignition_training failed: $positives; build it with services/pipelines/jobs/reignition_features.py"
    return
  fi
  if [[ "$positives" =~ ^[0-9]+$ ]] && (( positives >= MIN_POSITIVES )); then
    pass P3 "$positives positives in the train split"
    return
  fi
  fail P3 "$positives positives in the train split, need $MIN_POSITIVES; widen the label window per requirements.md §18"
}

count_objects() {
  gcloud storage ls "$1" 2>/dev/null | grep -c . || true
}

labels_rows() {
  awk -F, '
    NR == 1 { for (i = 1; i <= NF; i++) col[$i] = i; next }
    NF > 0 { print $(col["object_path"]) "," $(col["licence"]) }
  ' "$1" | tr -d '\r'
}

labels_problem() {
  local labels="$1" listing="$2" bucket="$3" header path licence
  header="$(head -1 "$labels" | tr -d '\r')"
  if [[ ",$header," != *,object_path,* || ",$header," != *,licence,* ]]; then
    echo "labels.csv needs the columns object_path and licence"
    return
  fi
  while IFS=, read -r path licence; do
    if [[ -z "$licence" ]]; then echo "no licence for $path"; return; fi
    if ! grep -qxF "$bucket/$path" <<<"$listing"; then echo "$path is not in $bucket/"; return; fi
  done < <(labels_rows "$labels")
}

check_p4() {
  local bucket="gs://$PROJECT-bara-exports/eval" labels photos voice listing problem
  labels="$(repo_root)/data/eval/labels.csv"
  photos="$(count_objects "$bucket/photos/")"
  voice="$(count_objects "$bucket/voice/")"
  if (( photos < MIN_PHOTOS || photos > MAX_PHOTOS )); then
    fail P4 "$photos photos in $bucket/photos/, need $MIN_PHOTOS to $MAX_PHOTOS"
    return
  fi
  if (( voice < MIN_VOICE )); then
    fail P4 "$voice voice notes in $bucket/voice/, need at least $MIN_VOICE"
    return
  fi
  if [[ ! -f "$labels" ]]; then
    fail P4 "data/eval/labels.csv is missing"
    return
  fi
  listing="$(gcloud storage ls -r "$bucket/**" 2>/dev/null || true)"
  problem="$(labels_problem "$labels" "$listing" "$bucket")"
  if [[ -n "$problem" ]]; then
    fail P4 "$problem"
    return
  fi
  pass P4 "$photos photos and $voice voice notes, every labelled file exists and has a licence"
}

main() {
  local check
  parse_args "$@"
  require_tools gcloud bq curl
  PROJECT="$(resolve_project "$PROJECT_FLAG")"
  require_project "$PROJECT"
  for check in "${CHECKS[@]}"; do
    "check_${check,,}"
  done
  exit "$FAILED"
}

main "$@"
