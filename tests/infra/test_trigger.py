from conftest import CI_ACCOUNT, PROJECT, REGION

SCRIPT = "infra/trigger.sh"
REPOSITORY = f"projects/{PROJECT}/locations/{REGION}/connections/github/repositories/bara"
TRIGGER_EXISTS = "builds triggers describe bara-main"


def test_no_arguments_prints_help_and_exits_2(run_script):
    result = run_script(SCRIPT)
    assert result.code == 2
    assert "--repository" in result.err


def test_help_lists_the_flags_and_exits_0(run_script):
    result = run_script(SCRIPT, "--help")
    assert result.code == 0
    for flag in ("--project", "--repository", "--dry-run"):
        assert flag in result.out


def test_unknown_flag_exits_2(run_script):
    assert run_script(SCRIPT, "--bogus").code == 2


def test_missing_repository_exits_2_and_names_the_flag(run_script):
    result = run_script(SCRIPT, "--project", PROJECT)
    assert result.code == 2
    assert "--repository" in result.err


def test_flag_without_value_exits_2(run_script):
    assert run_script(SCRIPT, "--repository").code == 2


def test_no_project_exits_3(run_script):
    result = run_script(SCRIPT, "--repository", REPOSITORY)
    assert result.code == 3


def test_no_gcloud_exits_4(run_script, bare_bin):
    result = run_script(SCRIPT, "--project", PROJECT, "--repository", REPOSITORY, path=bare_bin)
    assert result.code == 4


def test_dry_run_reports_would_make_and_creates_nothing(run_script):
    result = run_script(SCRIPT, "--project", PROJECT, "--repository", REPOSITORY, "--dry-run")
    assert result.code == 0
    assert [(r.state, r.name) for r in result.reports()] == [("would make", "bara-main")]
    assert not [call for call in result.calls if "create" in call]


def test_existing_trigger_reports_ok_and_creates_nothing(run_script):
    result = run_script(
        SCRIPT, "--project", PROJECT, "--repository", REPOSITORY, ok_pattern=TRIGGER_EXISTS
    )
    assert result.code == 0
    assert [(r.state, r.name) for r in result.reports()] == [("ok", "bara-main")]
    assert not [call for call in result.calls if "create" in call]


def test_missing_trigger_is_created_with_the_build_service_account(run_script):
    result = run_script(SCRIPT, "--project", PROJECT, "--repository", REPOSITORY)
    assert result.code == 0
    assert [(r.state, r.name) for r in result.reports()] == [("made", "bara-main")]
    created = [call for call in result.calls if "builds triggers create github" in call]
    assert len(created) == 1
    expected = [
        "--name=bara-main",
        f"--region={REGION}",
        f"--repository={REPOSITORY}",
        "--branch-pattern=^main$",
        "--build-config=cloudbuild.yaml",
        f"--service-account=projects/{PROJECT}/serviceAccounts/{CI_ACCOUNT}",
        f"--project={PROJECT}",
    ]
    for flag in expected:
        assert flag in created[0].split()
