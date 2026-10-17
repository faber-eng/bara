#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/../scripts/lib/project.sh"
source "$(dirname "${BASH_SOURCE[0]}")/../scripts/lib/ensure.sh"

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
readonly API_SERVICE=bara-api
readonly IMAGE_REPO=bara
readonly CI_SECRETS=(maps-key firebase-web-config)
readonly CI_PROJECT_ROLES=(
  roles/logging.logWriter roles/firebasehosting.admin roles/serviceusage.serviceUsageConsumer
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

The Cloud Build service account bara-build and its grants need the deployed bara-api
service and the secrets maps-key and firebase-web-config. Push subscriptions, Cloud
Scheduler jobs and run.invoker grants wait for the bara-api event route and bara-jobs.
EOF
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --project)
        require_flag_value "$1" "$#"
        PROJECT_FLAG="$2"; shift 2 ;;
      --dry-run) DRY_RUN=true; shift ;;
      -h|--help) usage; exit 0 ;;
      *) echo "unknown argument: $1" >&2; usage >&2; exit "$EXIT_USAGE" ;;
    esac
  done
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

split_binding() {
  local rest="${1#*|}"
  BINDING_NAME="${1%%|*}"
  BINDING_MEMBER="${rest%%|*}"
  BINDING_ROLE="${rest##*|}"
}

has_repo_role() {
  split_binding "$1"
  policy_has_binding "$BINDING_ROLE" "$BINDING_MEMBER" \
    gcloud artifacts repositories get-iam-policy "$BINDING_NAME" --location "$REGION" --project "$PROJECT"
}

grant_repo_role() {
  split_binding "$1"
  with_retry gcloud artifacts repositories add-iam-policy-binding "$BINDING_NAME" --location "$REGION" \
    --project "$PROJECT" --member "serviceAccount:$BINDING_MEMBER" --role "$BINDING_ROLE" --quiet --format none
}

has_service_role() {
  split_binding "$1"
  policy_has_binding "$BINDING_ROLE" "$BINDING_MEMBER" \
    gcloud run services get-iam-policy "$BINDING_NAME" --region "$REGION" --project "$PROJECT"
}

grant_service_role() {
  split_binding "$1"
  with_retry gcloud run services add-iam-policy-binding "$BINDING_NAME" --region "$REGION" \
    --project "$PROJECT" --member "serviceAccount:$BINDING_MEMBER" --role "$BINDING_ROLE" --quiet --format none
}

has_sa_user() {
  split_binding "$1"
  policy_has_binding "$BINDING_ROLE" "$BINDING_MEMBER" \
    gcloud iam service-accounts get-iam-policy "$BINDING_NAME" --project "$PROJECT"
}

grant_sa_user() {
  split_binding "$1"
  with_retry gcloud iam service-accounts add-iam-policy-binding "$BINDING_NAME" --project "$PROJECT" \
    --member "serviceAccount:$BINDING_MEMBER" --role "$BINDING_ROLE" --quiet --format none
}

has_secret_role() {
  split_binding "$1"
  policy_has_binding "$BINDING_ROLE" "$BINDING_MEMBER" \
    gcloud secrets get-iam-policy "$BINDING_NAME" --project "$PROJECT"
}

grant_secret_role() {
  split_binding "$1"
  with_retry gcloud secrets add-iam-policy-binding "$BINDING_NAME" --project "$PROJECT" \
    --member "serviceAccount:$BINDING_MEMBER" --role "$BINDING_ROLE" --quiet --format none
}

require_api_service() {
  if ! gcloud run services describe "$API_SERVICE" --region "$REGION" --project "$PROJECT" >/dev/null 2>&1; then
    echo "Cloud Run service $API_SERVICE not found in $REGION" >&2
    echo "deploy it once, then run infra/setup.sh again" >&2
    exit 1
  fi
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

setup_tasks_invoker_grant() {
  local api invoker
  api="$(sa_email bara-api)"
  invoker="$(sa_email bara-tasks-invoker)"
  ensure sa-user "$invoker|$api|roles/iam.serviceAccountUser" has_sa_user grant_sa_user
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

setup_ci() {
  local ci api role secret
  ci="$(sa_email "$CI_ACCOUNT")"
  api="$(sa_email bara-api)"
  require_api_service
  ensure service-account "$CI_ACCOUNT" sa_exists create_sa
  for role in "${CI_PROJECT_ROLES[@]}"; do
    ensure project-role "$ci|$role" has_project_role grant_project_role
  done
  ensure repo-role "$IMAGE_REPO|$ci|roles/artifactregistry.writer" has_repo_role grant_repo_role
  ensure service-role "$API_SERVICE|$ci|roles/run.developer" has_service_role grant_service_role
  ensure sa-user "$api|$ci|roles/iam.serviceAccountUser" has_sa_user grant_sa_user
  for secret in "${CI_SECRETS[@]}"; do
    ensure secret-role "$secret|$ci|roles/secretmanager.secretAccessor" has_secret_role grant_secret_role
  done
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
  setup_tasks_invoker_grant
  setup_buckets
  setup_data_stores
  setup_messaging
  setup_ci
}

main "$@"
