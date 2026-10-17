from conftest import PROJECT

SCRIPT = "infra/setup.sh"
SERVICE_EXISTS = "run services describe bara-api"
INVOKER = f"bara-tasks-invoker@{PROJECT}.iam.gserviceaccount.com"
SUBSCRIPTION = "drying.ranked.push"
EVIDENCE_SUBSCRIPTION = "evidence.received.push"

EXPECTED_PUSH_ITEMS = [
    ("api-timeout", "600"),
    ("service-role", f"bara-api|{INVOKER}|roles/run.invoker"),
    ("subscription", SUBSCRIPTION),
    ("subscription", EVIDENCE_SUBSCRIPTION),
]


def push_reports(result):
    wanted = set(EXPECTED_PUSH_ITEMS)
    return {
        (r.kind, r.name): r.state
        for r in result.reports()
        if (r.kind, r.name) in wanted
    }


def dry_run(run_script, **kwargs):
    return run_script(
        SCRIPT, "--project", PROJECT, "--dry-run", ok_pattern=SERVICE_EXISTS, **kwargs
    )


def test_dry_run_reports_the_push_items_as_would_make(run_script):
    result = dry_run(run_script)

    assert result.code == 0
    assert push_reports(result) == {item: "would make" for item in EXPECTED_PUSH_ITEMS}


def test_dry_run_grants_the_pubsub_agent_its_three_roles(run_script):
    result = dry_run(run_script)

    names = [r.name for r in result.reports()]
    agent_grants = sorted(name.split("|", 2)[2] for name in names if "gcp-sa-pubsub" in name)
    assert agent_grants == [
        "roles/iam.serviceAccountTokenCreator",
        "roles/pubsub.publisher",
        "roles/pubsub.subscriber",
        "roles/pubsub.subscriber",
    ]


def test_dry_run_creates_no_subscription_and_changes_no_service(run_script):
    result = dry_run(run_script)

    mutating = [
        c
        for c in result.calls
        if "subscriptions create" in c or "services update" in c
    ]
    assert mutating == []


def test_the_subscription_report_comes_from_the_same_ensure_as_a_real_run(run_script):
    result = run_script(
        SCRIPT,
        "--project",
        PROJECT,
        "--dry-run",
        ok_pattern="describe",
    )

    assert result.states_of("subscription", SUBSCRIPTION) == ["ok"]
    assert result.states_of("api-timeout", "600") == ["would make"]


def test_a_real_run_creates_the_push_subscription_with_oidc_ack_deadline_and_dlq(
    run_script,
):
    result = run_script(SCRIPT, "--project", PROJECT, ok_pattern=SERVICE_EXISTS)

    created = [c for c in result.calls if "pubsub subscriptions create" in c]
    assert len(created) == 2
    call = created[0]
    assert call.startswith(f"pubsub subscriptions create {SUBSCRIPTION} ")
    assert "--topic drying.ranked" in call
    assert f"--push-auth-service-account {INVOKER}" in call
    assert "--ack-deadline 600" in call
    assert f"--dead-letter-topic projects/{PROJECT}/topics/bara.dlq" in call
    assert "--max-delivery-attempts 5" in call


def test_a_real_run_pushes_evidence_received_to_its_own_endpoint(run_script):
    result = run_script(SCRIPT, "--project", PROJECT, ok_pattern=SERVICE_EXISTS)

    [call] = [
        c
        for c in result.calls
        if c.startswith(f"pubsub subscriptions create {EVIDENCE_SUBSCRIPTION} ")
    ]
    assert "--topic evidence.received" in call
    assert "/api/events/evidence.received" in call


def test_a_real_run_raises_the_api_request_timeout_to_600(run_script):
    result = run_script(SCRIPT, "--project", PROJECT, ok_pattern=SERVICE_EXISTS)

    updates = [c for c in result.calls if "run services update bara-api" in c]
    assert len(updates) == 1
    assert "--timeout 600" in updates[0]
