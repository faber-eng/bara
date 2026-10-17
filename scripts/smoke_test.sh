#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/lib/project.sh"

readonly EXIT_STEP_FAILED=1
readonly CASE_WAIT_SECONDS="${BARA_SMOKE_CASE_WAIT:-240}"
readonly VERDICT_WAIT_SECONDS="${BARA_SMOKE_VERDICT_WAIT:-150}"
readonly POLL_SECONDS="${BARA_SMOKE_POLL:-4}"
readonly OUTCOME_WAIT_SECONDS="${BARA_SMOKE_OUTCOME_WAIT:-90}"
readonly SAMPLE_ID=broken-dam-1

URL=""
PROJECT_FLAG=""
DRY_RUN=false
CONFIRMED=false
TOKEN=""
STEP=0
BEFORE_IDS=""
CURL=(curl -sS --connect-timeout 10 --max-time 60)

usage() {
  cat <<'EOF'
Usage: scripts/smoke_test.sh --yes [--url <base>] [--project <id>]
       scripts/smoke_test.sh --dry-run

Runs the Bara demo path against a live deployment with the judge header:
reset, trigger drying.ranked, wait for the cases, upload the broken-dam sample
photo, wait for the verdict, advance the clock past the deadline of a second case,
check that case is overdue or escalated.

It resets the scenario, so it needs --yes. Reset only touches example data.

  --yes           run the steps (the reset deletes and reseeds example data)
  --dry-run       print the steps, call nothing
  --url <base>    site to test (default: https://<project>.web.app)
  --project <id>  project (default: $PROJECT, then .secrets/bara.env)
  -h, --help      show this help

Environment: BARA_SMOKE_TOKEN is a Firebase ID token to use instead of signing in
anonymously. FIREBASE_API_KEY is the web API key for the anonymous sign-in
(default: read from the deployed site). BARA_SMOKE_CASE_WAIT, BARA_SMOKE_VERDICT_WAIT,
BARA_SMOKE_OUTCOME_WAIT and BARA_SMOKE_POLL change the waits, in seconds.

stdout: one "ok" or "FAIL" line per step. stderr: the reason for a failure.
Exit codes: 0 every step passed, 1 a step failed,
2 usage error, 3 no project.
EOF
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --yes) CONFIRMED=true; shift ;;
      --dry-run) DRY_RUN=true; shift ;;
      --url)
        [[ $# -ge 2 ]] || { echo "--url needs a value" >&2; exit "$EXIT_USAGE"; }
        URL="$2"; shift 2 ;;
      --project)
        [[ $# -ge 2 ]] || { echo "--project needs a value" >&2; exit "$EXIT_USAGE"; }
        PROJECT_FLAG="$2"; shift 2 ;;
      -h|--help) usage; exit 0 ;;
      *) echo "unknown argument: $1" >&2; usage >&2; exit "$EXIT_USAGE" ;;
    esac
  done
}

pass() {
  STEP=$((STEP + 1))
  printf 'ok    %d %s\n' "$STEP" "$1"
}

fail() {
  STEP=$((STEP + 1))
  printf 'FAIL  %d %s\n' "$STEP" "$1"
  echo "step $STEP failed: $1" >&2
  [[ -n "${2:-}" ]] && echo "$2" >&2
  exit "$EXIT_STEP_FAILED"
}

json_get() {
  python3 -c '
import json, sys
value = json.load(sys.stdin)
for part in sys.argv[1].split("."):
    if part == "":
        continue
    value = value[int(part)] if isinstance(value, list) else value[part]
print("" if value is None else value)
' "$1"
}

call() {
  local method="$1" path="$2" role="$3" body="${4:-}" out status
  out="$(mktemp)"
  local args=(-o "$out" -w '%{http_code}' -X "$method" "$URL$path"
    -H "Authorization: Bearer $TOKEN" -H "X-Bara-Role: $role")
  if [[ -n "$body" ]]; then
    args+=(-H 'content-type: application/json' --data "$body")
  fi
  status="$("${CURL[@]}" "${args[@]}" || true)"
  CALL_BODY="$(cat "$out")"
  rm -f "$out"
  CALL_STATUS="$status"
}

expect_status() {
  local wanted="$1" label="$2"
  [[ "$CALL_STATUS" == "$wanted" ]] || fail "$label" "wanted HTTP $wanted, got $CALL_STATUS: ${CALL_BODY:0:300}"
}

firebase_key() {
  if [[ -n "${FIREBASE_API_KEY:-}" ]]; then echo "$FIREBASE_API_KEY"; return; fi
  local page script bundle found
  page="$("${CURL[@]}" "$URL/" || true)"
  for script in $(grep -o '/assets/[^"]*\.js' <<<"$page" | sort -u); do
    bundle="$("${CURL[@]}" "$URL$script" || true)"
    found="$(grep -o -m1 'FIREBASE_API_KEY:.AIza[0-9A-Za-z_-]\{35\}' <<<"$bundle" | head -1 | grep -o 'AIza.*' || true)"
    if [[ -n "$found" ]]; then echo "$found"; return; fi
  done
}

sign_in() {
  if [[ -n "${BARA_SMOKE_TOKEN:-}" ]]; then TOKEN="$BARA_SMOKE_TOKEN"; return; fi
  local key response
  key="$(firebase_key)"
  [[ -n "$key" ]] || fail "sign in" "no Firebase web key: set FIREBASE_API_KEY or BARA_SMOKE_TOKEN"
  response="$("${CURL[@]}" "https://identitytoolkit.googleapis.com/v1/accounts:signUp?key=$key" \
    -H 'content-type: application/json' -d '{"returnSecureToken":true}')"
  TOKEN="$(json_get idToken <<<"$response" 2>/dev/null || true)"
  [[ -n "$TOKEN" ]] || fail "sign in" "anonymous sign-in returned no token: ${response:0:300}"
}

poll() {
  local seconds="$1"
  shift
  local waited=0
  while ! "$@"; do
    waited=$((waited + POLL_SECONDS))
    [[ $waited -le $seconds ]] || return 1
    sleep "$POLL_SECONDS"
  done
}

cases_assigned() {
  call GET "/api/cases?region=riau" ops
  [[ "$CALL_STATUS" == 200 ]] || return 1
  CASE_COUNT="$(new_assigned_ids | wc -l | tr -d ' ')"
  [[ "$CASE_COUNT" -ge 2 ]]
}

new_assigned_ids() {
  BEFORE="$BEFORE_IDS" python3 -c '
import json, os, sys
before = set(os.environ["BEFORE"].split())
for r in json.load(sys.stdin):
    case = r["case"]
    if case["example"] and case["id"] not in before and case["status"] == "assigned" and r["task_status"] == "open":
        print(case["id"])
' <<<"$CALL_BODY"
}

verdict_ready() {
  call GET "/api/cases/$CASE_ID" ops
  [[ "$CALL_STATUS" == 200 ]] || return 1
  VERDICT_STATE="$(python3 -c '
import json, sys
detail = json.load(sys.stdin)
for item in detail["evidence"]:
    if item["id"] == sys.argv[1] and item["verdict"] is not None:
        print(item["verdict"]["dam_state"])
        break
' "$EVIDENCE_ID" <<<"$CALL_BODY")"
  [[ -n "$VERDICT_STATE" ]]
}

step_health() {
  local response
  response="$("${CURL[@]}" "$URL/api/health" || true)"
  [[ "$(json_get status <<<"$response" 2>/dev/null || true)" == ok ]] || fail "health" "GET $URL/api/health did not answer ok"
  pass "health, git_sha $(json_get git_sha <<<"$response")"
}

step_reset() {
  call POST /api/judge/reset judge
  expect_status 200 "reset"
  remember_cases
  [[ "$(json_get offset_seconds <<<"$CALL_BODY")" == 0 ]] || fail "reset" "clock offset is not 0: $CALL_BODY"
  pass "reset, clock offset 0"
}

remember_cases() {
  local reset_body="$CALL_BODY"
  call GET "/api/cases?region=riau" ops
  expect_status 200 "read cases after reset"
  BEFORE_IDS="$(python3 -c '
import json, sys
print(" ".join(r["case"]["id"] for r in json.load(sys.stdin)))
' <<<"$CALL_BODY")"
  CALL_BODY="$reset_body"
}

step_trigger() {
  call POST /api/judge/trigger judge '{"event":"drying.ranked"}'
  expect_status 202 "trigger drying.ranked"
  pass "trigger drying.ranked, message $(json_get message_id <<<"$CALL_BODY")"
}

step_cases() {
  poll "$CASE_WAIT_SECONDS" cases_assigned || fail "cases assigned" "fewer than 2 assigned cases with an open task within ${CASE_WAIT_SECONDS}s; check the drying.ranked.push subscription and bara.dlq"
  CASE_ID="$(new_assigned_ids | sed -n 1p)"
  OTHER_ID="$(new_assigned_ids | sed -n 2p)"
  pass "$CASE_COUNT case(s) assigned, evidence on $CASE_ID, deadline check on $OTHER_ID"
}

step_task() {
  call GET "/api/cases/$CASE_ID" ops
  expect_status 200 "read case"
  local task
  task="$(python3 -c '
import json, sys
for task in json.load(sys.stdin)["tasks"]:
    if task["status"] == "open":
        print(json.dumps(task))
        break
' <<<"$CALL_BODY")" || fail "read case" "unreadable case: ${CALL_BODY:0:300}"
  [[ -n "$task" ]] || fail "read case" "no open task on $CASE_ID: ${CALL_BODY:0:300}"
  TASK_ID="$(json_get id <<<"$task")"
  ASSIGNEE="$(json_get assignee_id <<<"$task")"
  TARGET_LAT="$(json_get target.lat <<<"$task")"
  TARGET_LON="$(json_get target.lon <<<"$task")"
  pass "task $TASK_ID given to $ASSIGNEE"
}

step_upload() {
  local sample size ticket upload_url put_status
  sample="$(mktemp)"
  "${CURL[@]}" -f -o "$sample" "$URL/api/samples/$SAMPLE_ID/file" || fail "download sample" "GET /api/samples/$SAMPLE_ID/file failed"
  size="$(wc -c <"$sample" | tr -d ' ')"
  [[ "$size" -gt 0 ]] || fail "download sample" "the sample file is empty"
  [[ "$(head -c 2 "$sample" | od -An -tx1 | tr -d ' \n')" == ffd8 ]] || fail "download sample" "the sample is not a JPEG"
  call POST "/api/v/$ASSIGNEE/uploads" volunteer \
    "{\"task_id\":\"$TASK_ID\",\"kind\":\"photo\",\"content_type\":\"image/jpeg\",\"size_bytes\":$size,\"sample\":true}"
  expect_status 200 "request upload"
  EVIDENCE_ID="$(json_get evidence_id <<<"$CALL_BODY")"
  upload_url="$(json_get upload_url <<<"$CALL_BODY")"
  local header_args=() line
  while IFS= read -r line; do
    header_args+=("$line")
  done < <(python3 -c '
import json, sys
for key, value in json.load(sys.stdin)["headers"].items():
    print("-H")
    print(f"{key}: {value}")
' <<<"$CALL_BODY")
  put_status="$(curl -sS --connect-timeout 10 --max-time 120 -o /dev/null -w '%{http_code}' -X PUT ${header_args[@]+"${header_args[@]}"} --data-binary "@$sample" "$upload_url" || true)"
  rm -f "$sample"
  [[ "$put_status" == 200 ]] || fail "upload to storage" "PUT returned HTTP $put_status"
  call POST "/api/v/$ASSIGNEE/evidence/$EVIDENCE_ID/complete" volunteer \
    "{\"point\":{\"lat\":$TARGET_LAT,\"lon\":$TARGET_LON},\"captured_at\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"}"
  expect_status 200 "complete upload"
  pass "uploaded sample $SAMPLE_ID as evidence $EVIDENCE_ID"
}

step_verdict() {
  poll "$VERDICT_WAIT_SECONDS" verdict_ready || fail "verdict" "no verdict within ${VERDICT_WAIT_SECONDS}s; check the evidence.received.push subscription"
  [[ "$VERDICT_STATE" == broken ]] || fail "verdict" "dam_state is $VERDICT_STATE, wanted broken"
  pass "verdict dam_state broken"
}

step_deadline() {
  call GET "/api/cases/$OTHER_ID" ops
  expect_status 200 "read $OTHER_ID"
  OTHER_DEADLINE="$(python3 -c '
import json, sys
for task in json.load(sys.stdin)["tasks"]:
    if task["status"] == "open":
        print(task["deadline_at"])
        break
' <<<"$CALL_BODY")" || fail "read deadline" "unreadable case: ${CALL_BODY:0:300}"
  [[ -n "$OTHER_DEADLINE" ]] || fail "read deadline" "no open task on $OTHER_ID: ${CALL_BODY:0:300}"
  pass "task on $OTHER_ID is due $OTHER_DEADLINE"
}

hours_past_deadline() {
  python3 -c '
import json, math, sys
from datetime import datetime
now = datetime.fromisoformat(json.load(sys.stdin)["now"])
deadline = datetime.fromisoformat(sys.argv[1])
print(max(1, math.ceil((deadline - now).total_seconds() / 3600) + 1))
' "$OTHER_DEADLINE"
}

step_advance() {
  call GET /api/clock ops
  expect_status 200 "read clock"
  ADVANCE_HOURS="$(hours_past_deadline <<<"$CALL_BODY")" || fail "advance" "cannot compute hours from: ${CALL_BODY:0:300}"
  call POST /api/judge/advance judge "{\"hours\":$ADVANCE_HOURS}"
  expect_status 200 "advance ${ADVANCE_HOURS}h"
  [[ "$(json_get offset_seconds <<<"$CALL_BODY")" -ge $((ADVANCE_HOURS * 3600)) ]] || fail "advance" "offset is smaller than ${ADVANCE_HOURS}h: $CALL_BODY"
  pass "advanced ${ADVANCE_HOURS}h, past the deadline of $OTHER_ID"
}

case_overdue() {
  call GET "/api/cases/$OTHER_ID" ops
  [[ "$CALL_STATUS" == 200 ]] || return 1
  CASE_STATUS="$(json_get case.status <<<"$CALL_BODY")"
  [[ "$CASE_STATUS" == overdue || "$CASE_STATUS" == escalated ]]
}

step_outcome() {
  poll "$OUTCOME_WAIT_SECONDS" case_overdue || fail "outcome" "$OTHER_ID is $CASE_STATUS, wanted overdue or escalated after +${ADVANCE_HOURS}h"
  pass "$OTHER_ID is $CASE_STATUS after +${ADVANCE_HOURS}h"
}

print_plan() {
  cat <<EOF
would run against $URL:
  1 health
  2 sign in anonymously (or use BARA_SMOKE_TOKEN)
  3 POST /api/judge/reset
  4 POST /api/judge/trigger {"event":"drying.ranked"}
  5 wait for an assigned case with an open task (up to ${CASE_WAIT_SECONDS}s)
  6 upload sample $SAMPLE_ID for the task and complete it
  7 wait for the verdict, expect dam_state broken (up to ${VERDICT_WAIT_SECONDS}s)
  8 read the deadline of a second assigned case
  9 POST /api/judge/advance past that deadline
  10 expect that case overdue or escalated
EOF
}

finish() {
  echo "smoke test passed"
}

main() {
  parse_args "$@"
  if [[ "$DRY_RUN" != true && "$CONFIRMED" != true ]]; then
    echo "pass --yes to run: the reset deletes and reseeds example data" >&2
    usage >&2
    exit "$EXIT_USAGE"
  fi
  if [[ -z "$URL" ]]; then
    local project
    project="$(resolve_project "$PROJECT_FLAG")"
    require_project "$project"
    URL="https://${project}.web.app"
  fi
  URL="${URL%/}"
  if [[ "$DRY_RUN" == true ]]; then print_plan; exit 0; fi
  step_health
  sign_in
  step_reset
  step_trigger
  step_cases
  step_task
  step_upload
  step_verdict
  step_deadline
  step_advance
  step_outcome
  finish
}

main "$@"
