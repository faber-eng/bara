from conftest import CI_ACCOUNT, PROJECT

SCRIPT = "infra/setup.sh"
API_ACCOUNT = f"bara-api@{PROJECT}.iam.gserviceaccount.com"
SERVICE_EXISTS = "run services describe bara-api"

CI_PROJECT_ROLES = [
    "roles/logging.logWriter",
    "roles/firebasehosting.admin",
    "roles/serviceusage.serviceUsageConsumer",
]
CI_SECRETS = ["maps-key", "firebase-web-config"]

EXPECTED_CI_ITEMS = (
    [("service-account", "bara-build")]
    + [("project-role", f"{CI_ACCOUNT}|{role}") for role in CI_PROJECT_ROLES]
    + [("repo-role", f"bara|{CI_ACCOUNT}|roles/artifactregistry.writer")]
    + [("service-role", f"bara-api|{CI_ACCOUNT}|roles/run.developer")]
    + [("sa-user", f"{API_ACCOUNT}|{CI_ACCOUNT}|roles/iam.serviceAccountUser")]
    + [
        ("secret-role", f"{secret}|{CI_ACCOUNT}|roles/secretmanager.secretAccessor")
        for secret in CI_SECRETS
    ]
)

ALL_BINDINGS_PRESENT = "\n".join(
    f"{role},serviceAccount:{CI_ACCOUNT}"
    for role in CI_PROJECT_ROLES
    + [
        "roles/artifactregistry.writer",
        "roles/run.developer",
        "roles/iam.serviceAccountUser",
        "roles/secretmanager.secretAccessor",
    ]
)


def ci_reports(result):
    wanted = set(EXPECTED_CI_ITEMS)
    return {(r.kind, r.name): r.state for r in result.reports() if (r.kind, r.name) in wanted}


def test_dry_run_reports_every_ci_item_as_would_make(run_script):
    result = run_script(SCRIPT, "--project", PROJECT, "--dry-run", ok_pattern=SERVICE_EXISTS)
    assert result.code == 0
    assert ci_reports(result) == {item: "would make" for item in EXPECTED_CI_ITEMS}


def test_dry_run_changes_nothing(run_script):
    result = run_script(SCRIPT, "--project", PROJECT, "--dry-run", ok_pattern=SERVICE_EXISTS)
    mutating = [c for c in result.calls if "add-iam-policy-binding" in c or " create " in c]
    assert mutating == []


def test_second_run_reports_every_ci_item_as_ok(run_script):
    result = run_script(
        SCRIPT,
        "--project",
        PROJECT,
        "--dry-run",
        ok_pattern="describe",
        policy=ALL_BINDINGS_PRESENT,
    )
    assert result.code == 0
    assert ci_reports(result) == {item: "ok" for item in EXPECTED_CI_ITEMS}


def test_missing_api_service_exits_1_and_names_it(run_script):
    result = run_script(SCRIPT, "--project", PROJECT, "--dry-run")
    assert result.code == 1
    assert "bara-api" in result.err


def test_real_run_grants_each_role_on_the_narrowest_resource(run_script):
    result = run_script(SCRIPT, "--project", PROJECT, ok_pattern=SERVICE_EXISTS)
    assert result.code == 0
    grants = [c for c in result.calls if "add-iam-policy-binding" in c and CI_ACCOUNT in c]
    expected = [
        ("projects add-iam-policy-binding", "roles/logging.logWriter"),
        ("projects add-iam-policy-binding", "roles/firebasehosting.admin"),
        ("projects add-iam-policy-binding", "roles/serviceusage.serviceUsageConsumer"),
        ("artifacts repositories add-iam-policy-binding bara", "roles/artifactregistry.writer"),
        ("run services add-iam-policy-binding bara-api", "roles/run.developer"),
        (f"iam service-accounts add-iam-policy-binding {API_ACCOUNT}", "roles/iam.serviceAccountUser"),
        ("secrets add-iam-policy-binding maps-key", "roles/secretmanager.secretAccessor"),
        ("secrets add-iam-policy-binding firebase-web-config", "roles/secretmanager.secretAccessor"),
    ]
    for command, role in expected:
        assert any(command in call and f"--role {role}" in call for call in grants), (command, role)
    assert len(grants) == len(expected)
    assert any("iam service-accounts create bara-build" in c for c in result.calls)
