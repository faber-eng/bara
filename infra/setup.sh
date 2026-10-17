#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/../scripts/lib/project.sh"

readonly REGION=asia-southeast1
readonly BQ_LOCATION=US
readonly DATASET=bara
readonly QUEUE=task-deadlines
readonly DLQ_TOPIC=bara.dlq
readonly TOPICS=(hotspot.detected fire.quiet drying.ranked evidence.received task.overdue case.escalated "$DLQ_TOPIC")
readonly APIS=(
  run cloudbuild artifactregistry aiplatform earthengine bigquery bigquerystorage pubsub cloudtasks
  cloudscheduler firestore storage secretmanager firebase firebasehosting identitytoolkit maps-backend
  cloudtrace logging iam cloudresourcemanager
)
readonly API_ROLES=(
  roles/aiplatform.user roles/datastore.user roles/pubsub.publisher roles/cloudtasks.enqueuer
  roles/bigquery.dataEditor roles/bigquery.jobUser roles/earthengine.writer roles/secretmanager.secretAccessor
)
readonly JOBS_ROLES=(
  roles/earthengine.writer roles/bigquery.dataEditor roles/bigquery.jobUser roles/datastore.user
  roles/pubsub.publisher roles/serviceusage.serviceUsageConsumer
)

DRY_RUN=false
PROJECT_FLAG=""

usage() {
  cat <<'EOF'
Usage: infra/setup.sh [--project <id>] [--dry-run]

Creates the Bara base resources in a Google Cloud project. Safe to run again:
anything that already exists is left as it is.

  --project <id>  project to set up (default: $PROJECT, then .secrets/bara.env)
  --dry-run       print what would be created, change nothing
  -h, --help      show this help

Prints one line per resource: "ok" (exists), "made" or "would make".
Exit codes: 0 done, 1 a gcloud call failed, 2 usage error, 3 no project, 4 tool missing.

Push subscriptions, Cloud Scheduler jobs and run.invoker grants need the deployed
bara-api and bara-jobs services; they are created by the Cloud Build step (OT-4).
EOF
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --project)
        [[ $# -ge 2 ]] || { echo "--project needs a value" >&2; exit "$EXIT_USAGE"; }
        PROJECT_FLAG="$2"; shift 2 ;;
      --dry-run) DRY_RUN=true; shift ;;
      -h|--help) usage; exit 0 ;;
      *) echo "unknown argument: $1" >&2; usage >&2; exit "$EXIT_USAGE" ;;
    esac
  done
}

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

policy_has_binding() {
  local role="$1" member="$2" policy
  shift 2
  policy="$("$@" --flatten='bindings[].members' --format='csv[no-heading](bindings.role,bindings.members)')"
  grep -qxF "$role,serviceAccount:$member" <<<"$policy"
}

with_retry() {
  local attempt
  for attempt in 1 2 3 4 5 6; do
    if "$@" >/dev/null 2>&1; then return 0; fi
    sleep $((attempt * 5))
  done
  "$@" >/dev/null
}

sa_email() {
  echo "$1@${PROJECT}.iam.gserviceaccount.com"
}

api_enabled() {
  grep -qx "$1.googleapis.com" <<<"$ENABLED_APIS"
}

enable_api() {
  gcloud services enable "$1.googleapis.com" --project "$PROJECT" --quiet >/dev/null
}

sa_exists() {
  gcloud iam service-accounts describe "$(sa_email "$1")" --project "$PROJECT" >/dev/null 2>&1
}

create_sa() {
  gcloud iam service-accounts create "$1" --project "$PROJECT" --display-name "$1" --quiet >/dev/null
}

has_project_role() {
  local member="${1%%|*}" role="${1##*|}"
  policy_has_binding "$role" "$member" gcloud projects get-iam-policy "$PROJECT"
}

grant_project_role() {
  local member="${1%%|*}" role="${1##*|}"
  with_retry gcloud projects add-iam-policy-binding "$PROJECT" --member "serviceAccount:$member" \
    --role "$role" --condition None --quiet --format none
}

bucket_exists() {
  gcloud storage buckets describe "gs://$1" --project "$PROJECT" >/dev/null 2>&1
}

create_bucket() {
  gcloud storage buckets create "gs://$1" --project "$PROJECT" --location "$REGION" \
    --uniform-bucket-level-access --quiet >/dev/null
}

has_bucket_role() {
  local bucket="${1%%|*}" rest="${1#*|}"
  local member="${rest%%|*}" role="${rest##*|}"
  policy_has_binding "$role" "$member" gcloud storage buckets get-iam-policy "gs://$bucket" --project "$PROJECT"
}

grant_bucket_role() {
  local bucket="${1%%|*}" rest="${1#*|}"
  local member="${rest%%|*}" role="${rest##*|}"
  with_retry gcloud storage buckets add-iam-policy-binding "gs://$bucket" --project "$PROJECT" \
    --member "serviceAccount:$member" --role "$role" --quiet
}

cors_origins() {
  echo "https://${PROJECT}.web.app https://${PROJECT}.firebaseapp.com http://localhost:5173"
}

has_cors() {
  local config origin
  config="$(gcloud storage buckets describe "gs://$1" --project "$PROJECT" --format='value(cors_config)')"
  [[ "$config" == *PUT* ]] || return 1
  for origin in $(cors_origins); do
    [[ "$config" == *"$origin"* ]] || return 1
  done
}

set_cors() {
  local file origins
  file="$(mktemp)"
  trap 'rm -f "$file"; trap - RETURN' RETURN
  origins="$(cors_origins)"
  origins="\"${origins// /\", \"}\""
  cat >"$file" <<EOF
[{"origin": [$origins], "method": ["PUT", "GET"], "responseHeader": ["Content-Type"], "maxAgeSeconds": 3600}]
EOF
  gcloud storage buckets update "gs://$1" --project "$PROJECT" --cors-file "$file" --quiet >/dev/null
}

has_self_token_creator() {
  policy_has_binding roles/iam.serviceAccountTokenCreator "$1" \
    gcloud iam service-accounts get-iam-policy "$1" --project "$PROJECT"
}

grant_self_token_creator() {
  with_retry gcloud iam service-accounts add-iam-policy-binding "$1" --project "$PROJECT" \
    --member "serviceAccount:$1" --role roles/iam.serviceAccountTokenCreator --quiet --format none
}

dataset_exists() {
  bq --project_id "$PROJECT" show --format none "$PROJECT:$1" >/dev/null 2>&1
}

create_dataset() {
  bq --project_id "$PROJECT" --location "$BQ_LOCATION" mk --dataset "$PROJECT:$1" >/dev/null
}

firestore_exists() {
  gcloud firestore databases describe --database "$1" --project "$PROJECT" >/dev/null 2>&1
}

create_firestore() {
  gcloud firestore databases create --database "$1" --location "$REGION" --type firestore-native \
    --project "$PROJECT" --quiet >/dev/null
}

topic_exists() {
  gcloud pubsub topics describe "$1" --project "$PROJECT" >/dev/null 2>&1
}

create_topic() {
  gcloud pubsub topics create "$1" --project "$PROJECT" --quiet >/dev/null
}

queue_exists() {
  gcloud tasks queues describe "$1" --location "$REGION" --project "$PROJECT" >/dev/null 2>&1
}

create_queue() {
  gcloud tasks queues create "$1" --location "$REGION" --project "$PROJECT" --quiet >/dev/null
}

load_enabled_apis() {
  ENABLED_APIS="$(gcloud services list --enabled --project "$PROJECT" --format='value(config.name)')"
}

setup_apis() {
  local api
  load_enabled_apis
  for api in "${APIS[@]}"; do
    ensure api "$api" api_enabled enable_api
  done
}

setup_service_accounts() {
  local name
  for name in bara-api bara-jobs bara-pubsub-invoker bara-tasks-invoker; do
    ensure service-account "$name" sa_exists create_sa
  done
}

setup_project_roles() {
  local role api jobs
  api="$(sa_email bara-api)"
  jobs="$(sa_email bara-jobs)"
  for role in "${API_ROLES[@]}"; do
    ensure project-role "$api|$role" has_project_role grant_project_role
  done
  for role in "${JOBS_ROLES[@]}"; do
    ensure project-role "$jobs|$role" has_project_role grant_project_role
  done
  ensure sa-role "$api" has_self_token_creator grant_self_token_creator
}

setup_buckets() {
  local evidence="${PROJECT}-bara-evidence" exports="${PROJECT}-bara-exports"
  ensure bucket "$evidence" bucket_exists create_bucket
  ensure bucket "$exports" bucket_exists create_bucket
  ensure bucket-cors "$evidence" has_cors set_cors
  ensure bucket-role "$evidence|$(sa_email bara-api)|roles/storage.objectAdmin" has_bucket_role grant_bucket_role
  ensure bucket-role "$exports|$(sa_email bara-jobs)|roles/storage.objectAdmin" has_bucket_role grant_bucket_role
}

setup_data_stores() {
  ensure bigquery "$DATASET" dataset_exists create_dataset
  ensure firestore "(default)" firestore_exists create_firestore
}

setup_messaging() {
  local topic
  for topic in "${TOPICS[@]}"; do
    ensure topic "$topic" topic_exists create_topic
  done
  ensure tasks-queue "$QUEUE" queue_exists create_queue
}

main() {
  parse_args "$@"
  require_tools gcloud bq
  PROJECT="$(resolve_project "$PROJECT_FLAG")"
  require_project "$PROJECT"
  echo "project: $PROJECT  dry-run: $DRY_RUN" >&2

  setup_apis
  setup_service_accounts
  setup_project_roles
  setup_buckets
  setup_data_stores
  setup_messaging
}

main "$@"
