from collections.abc import Sequence

from jobs import weekly_rankings
from jobs.cli import EXIT_FAILURE, EXIT_OK, EXIT_USAGE, run_steps


class Recorder:
    def __init__(self, calls: list[str], name: str, code: int = EXIT_OK) -> None:
        self.calls = calls
        self.name = name
        self.code = code
        self.argv: Sequence[str] | None = None

    def __call__(self, argv: Sequence[str] | None) -> int:
        self.calls.append(self.name)
        self.argv = argv
        return self.code


def test_runs_every_step_in_order_with_the_same_arguments():
    calls: list[str] = []
    first, second = Recorder(calls, "drying"), Recorder(calls, "publish")
    argv = ["--region", "riau", "--dry-run"]
    code = run_steps("weekly_rankings", argv, (("drying", first), ("publish", second)))
    assert code == EXIT_OK
    assert calls == ["drying", "publish"]
    assert first.argv == argv
    assert second.argv == argv


def test_a_failed_first_step_skips_publishing_and_keeps_its_exit_code():
    calls: list[str] = []
    first = Recorder(calls, "drying", EXIT_FAILURE)
    second = Recorder(calls, "publish")
    code = run_steps("weekly_rankings", [], (("drying", first), ("publish", second)))
    assert code == EXIT_FAILURE
    assert calls == ["drying"]


def test_a_usage_error_in_the_second_step_is_returned():
    calls: list[str] = []
    first = Recorder(calls, "drying")
    second = Recorder(calls, "publish", EXIT_USAGE)
    code = run_steps("weekly_rankings", [], (("drying", first), ("publish", second)))
    assert code == EXIT_USAGE
    assert calls == ["drying", "publish"]


class RegionRecorder:
    def __init__(self, calls: list[tuple[str, str]], name: str, failing=()) -> None:
        self.calls = calls
        self.name = name
        self.failing = failing

    def __call__(self, argv: Sequence[str] | None) -> int:
        region = argv[argv.index("--region") + 1]
        self.calls.append((self.name, region))
        return EXIT_FAILURE if region in self.failing else EXIT_OK


def wire(monkeypatch, failing=()):
    calls: list[tuple[str, str]] = []
    drying = RegionRecorder(calls, "d", failing)
    monkeypatch.setattr(weekly_rankings.drying_score, "main", drying)
    monkeypatch.setattr(
        weekly_rankings.publish_rankings, "main", RegionRecorder(calls, "p")
    )
    return calls


def test_without_a_region_flag_every_configured_region_runs(monkeypatch, config_dir):
    calls = wire(monkeypatch)
    assert weekly_rankings.main(["--config-dir", str(config_dir)]) == EXIT_OK
    assert calls == [
        ("d", "riau"),
        ("p", "riau"),
        ("d", "congo_cuvette"),
        ("p", "congo_cuvette"),
    ]


def test_a_region_flag_limits_the_run_to_that_region(monkeypatch, config_dir):
    calls = wire(monkeypatch)
    argv = ["--region", "congo_cuvette", "--config-dir", str(config_dir)]
    assert weekly_rankings.main(argv) == EXIT_OK
    assert calls == [("d", "congo_cuvette"), ("p", "congo_cuvette")]


def test_other_flags_reach_both_steps(monkeypatch, config_dir):
    seen: list[Sequence[str]] = []

    def record(argv: Sequence[str] | None) -> int:
        seen.append(list(argv or []))
        return EXIT_OK

    monkeypatch.setattr(weekly_rankings.drying_score, "main", record)
    monkeypatch.setattr(weekly_rankings.publish_rankings, "main", record)
    argv = ["--week", "2026-W42", "--dry-run", "--config-dir", str(config_dir)]
    assert weekly_rankings.main([*argv, "--region", "riau"]) == EXIT_OK
    assert len(seen) == 2
    for received in seen:
        assert "--week" in received
        assert "--dry-run" in received
        assert received[-2:] == ["--region", "riau"]


def test_a_failing_region_does_not_stop_the_next_one(monkeypatch, config_dir):
    calls = wire(monkeypatch, failing=("riau",))
    code = weekly_rankings.main(["--config-dir", str(config_dir)])
    assert code == EXIT_FAILURE
    assert calls == [("d", "riau"), ("d", "congo_cuvette"), ("p", "congo_cuvette")]


def test_a_failing_second_region_still_fails_the_job(monkeypatch, config_dir):
    wire(monkeypatch, failing=("congo_cuvette",))
    assert weekly_rankings.main(["--config-dir", str(config_dir)]) == EXIT_FAILURE


def test_an_unknown_region_is_a_usage_error(monkeypatch, config_dir):
    calls = wire(monkeypatch)
    argv = ["--region", "mars", "--config-dir", str(config_dir)]
    assert weekly_rankings.main(argv) == EXIT_USAGE
    assert calls == []
