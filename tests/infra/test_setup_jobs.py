from conftest import CI_ACCOUNT, PROJECT, REGION

SCRIPT = "infra/setup.sh"
SERVICE_EXISTS = "run services describe bara-api"
JOB_EXISTS = "run jobs describe bara-drying"
JOBS_ACCOUNT = f"bara-jobs@{PROJECT}.iam.gserviceaccount.com"
SCHEDULER_ACCOUNT = f"bara-scheduler@{PROJECT}.iam.gserviceaccount.com"
SCHEDULER_JOB = "bara-drying-weekly"
RUN_URI = (
    f"https://run.googleapis.com/v2/projects/{PROJECT}/locations/{REGION}"
    "/jobs/bara-drying:run"
)
INVOKER_POLICY = f"roles/run.invoker,serviceAccount:{SCHEDULER_ACCOUNT}"


def states(result, kind: str, name: str) -> list[str]:
    return [r.state for r in result.reports() if (r.kind, r.name) == (kind, name)]


def test_dry_run_reports_the_deploy_access_and_the_scheduler_job(run_script):
    result = run_script(
        SCRIPT, "--project", PROJECT, "--dry-run", ok_pattern=SERVICE_EXISTS
    )
    assert result.code == 0
    assert states(result, "service-account", "bara-scheduler") == ["would make"]
    assert states(result, "project-role", f"{CI_ACCOUNT}|roles/run.developer") == [
        "would make"
    ]
    assert states(
        result,
        "sa-user",
        f"{JOBS_ACCOUNT}|{CI_ACCOUNT}|roles/iam.serviceAccountUser",
    ) == ["would make"]
    assert states(result, "scheduler-job", SCHEDULER_JOB) == ["would make"]


def test_a_missing_cloud_run_job_skips_its_invoker_grant_with_a_hint(run_script):
    result = run_script(
        SCRIPT, "--project", PROJECT, "--dry-run", ok_pattern=SERVICE_EXISTS
    )
    assert result.code == 0
    assert [r for r in result.reports() if r.kind == "job-role"] == []
    assert "bara-drying" in result.err
    assert "run infra/setup.sh again" in result.err


def test_an_existing_cloud_run_job_gets_its_invoker_grant_reported(run_script):
    result = run_script(
        SCRIPT,
        "--project",
        PROJECT,
        "--dry-run",
        ok_pattern=f"{SERVICE_EXISTS}|{JOB_EXISTS}",
    )
    assert result.code == 0
    name = f"bara-drying|{SCHEDULER_ACCOUNT}|roles/run.invoker"
    assert states(result, "job-role", name) == ["would make"]


def test_everything_is_ok_on_a_second_run(run_script):
    result = run_script(
        SCRIPT,
        "--project",
        PROJECT,
        "--dry-run",
        ok_pattern="describe",
        policy=INVOKER_POLICY,
    )
    assert result.code == 0
    name = f"bara-drying|{SCHEDULER_ACCOUNT}|roles/run.invoker"
    assert states(result, "job-role", name) == ["ok"]
    assert states(result, "scheduler-job", SCHEDULER_JOB) == ["ok"]


def test_real_run_creates_the_scheduler_job_with_oauth_and_the_jakarta_zone(
    run_script,
):
    result = run_script(SCRIPT, "--project", PROJECT, ok_pattern=SERVICE_EXISTS)
    assert result.code == 0
    created = [
        c
        for c in result.calls
        if c.startswith(f"scheduler jobs create http {SCHEDULER_JOB}")
    ]
    assert len(created) == 1
    call = created[0]
    assert f"--location {REGION}" in call
    assert "--schedule 0 1 * * 1" in call
    assert "--time-zone Asia/Jakarta" in call
    assert f"--uri {RUN_URI}" in call
    assert "--http-method POST" in call
    assert f"--oauth-service-account-email {SCHEDULER_ACCOUNT}" in call
    assert "--oidc" not in call


def test_real_run_grants_run_invoker_on_the_job_to_the_scheduler_only(run_script):
    result = run_script(
        SCRIPT, "--project", PROJECT, ok_pattern=f"{SERVICE_EXISTS}|{JOB_EXISTS}"
    )
    assert result.code == 0
    grants = [c for c in result.calls if "run jobs add-iam-policy-binding" in c]
    assert len(grants) == 1
    assert "run jobs add-iam-policy-binding bara-drying" in grants[0]
    assert f"--member serviceAccount:{SCHEDULER_ACCOUNT}" in grants[0]
    assert "--role roles/run.invoker" in grants[0]
    assert not any("allUsers" in c for c in result.calls)


DAILY_JOB = "bara-reignition-daily"
DAILY_URI = (
    f"https://run.googleapis.com/v2/projects/{PROJECT}/locations/{REGION}"
    "/jobs/bara-reignition:run"
)


def test_dry_run_reports_the_daily_reignition_scheduler_job(run_script):
    result = run_script(
        SCRIPT, "--project", PROJECT, "--dry-run", ok_pattern=SERVICE_EXISTS
    )
    assert result.code == 0
    assert states(result, "scheduler-job", DAILY_JOB) == ["would make"]
    assert "bara-reignition" in result.err


def test_real_run_schedules_the_reignition_job_daily_in_jakarta(run_script):
    result = run_script(SCRIPT, "--project", PROJECT, ok_pattern=SERVICE_EXISTS)
    assert result.code == 0
    created = [
        c for c in result.calls if c.startswith(f"scheduler jobs create http {DAILY_JOB}")
    ]
    assert len(created) == 1
    assert "--schedule 0 6 * * *" in created[0]
    assert "--time-zone Asia/Jakarta" in created[0]
    assert f"--uri {DAILY_URI}" in created[0]


def test_an_existing_reignition_job_gets_its_invoker_grant(run_script):
    result = run_script(
        SCRIPT,
        "--project",
        PROJECT,
        ok_pattern=f"{SERVICE_EXISTS}|run jobs describe bara-reignition",
    )
    assert result.code == 0
    grants = [c for c in result.calls if "run jobs add-iam-policy-binding" in c]
    assert len(grants) == 1
    assert "run jobs add-iam-policy-binding bara-reignition" in grants[0]
    assert "--role roles/run.invoker" in grants[0]
