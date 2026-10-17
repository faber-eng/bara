#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/../scripts/lib/project.sh"
source "$(dirname "${BASH_SOURCE[0]}")/../scripts/lib/ensure.sh"

readonly TRIGGER=bara-main
readonly BRANCH_PATTERN='^main$'
readonly BUILD_CONFIG=cloudbuild.yaml

DRY_RUN=false
PROJECT_FLAG=""
REPOSITORY=""

usage() {
  cat <<'EOF_USAGE'
Usage: infra/trigger.sh --repository <resource> [--project <id>] [--dry-run]

Creates the Cloud Build trigger bara-main: a push to main runs cloudbuild.yaml as
the bara-build service account. Safe to run again: an existing trigger is left as it is.

  --repository <resource>  the connected GitHub repository, as
                           projects/<id>/locations/<region>/connections/<name>/repositories/<repo>
  --project <id>           project to use (default: $PROJECT, then .secrets/bara.env)
  --dry-run                print what would be created, change nothing
  -h, --help               show this help

Run infra/setup.sh first (it creates bara-build). Connect the GitHub repository once
in the Cloud Build console; that step needs a person to authorise GitHub.
Prints one line: "ok" (exists), "made" or "would make".
Exit codes: 0 done, 1 a gcloud call failed, 2 usage error, 3 no project, 4 tool missing.
EOF_USAGE
}

parse_args() {
  if [[ $# -eq 0 ]]; then usage >&2; exit "$EXIT_USAGE"; fi
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --project)
        require_flag_value "$1" "$#"
        PROJECT_FLAG="$2"; shift 2 ;;
      --repository)
        require_flag_value "$1" "$#"
        REPOSITORY="$2"; shift 2 ;;
      --dry-run) DRY_RUN=true; shift ;;
      -h|--help) usage; exit 0 ;;
      *) echo "unknown argument: $1" >&2; usage >&2; exit "$EXIT_USAGE" ;;
    esac
  done
  if [[ -z "$REPOSITORY" ]]; then
    echo "--repository is required" >&2
    exit "$EXIT_USAGE"
  fi
}

trigger_exists() {
  gcloud builds triggers describe "$1" --region "$REGION" --project "$PROJECT" >/dev/null 2>&1
}

create_trigger() {
  gcloud builds triggers create github --name="$1" --region="$REGION" --repository="$REPOSITORY" \
    --branch-pattern="$BRANCH_PATTERN" --build-config="$BUILD_CONFIG" \
    --service-account="projects/$PROJECT/serviceAccounts/$CI_ACCOUNT@$PROJECT.iam.gserviceaccount.com" \
    --project="$PROJECT" --quiet >/dev/null
}

main() {
  parse_args "$@"
  require_tools gcloud
  PROJECT="$(resolve_project "$PROJECT_FLAG")"
  require_project "$PROJECT"
  echo "project: $PROJECT  dry-run: $DRY_RUN" >&2

  ensure trigger "$TRIGGER" trigger_exists create_trigger
}

main "$@"
