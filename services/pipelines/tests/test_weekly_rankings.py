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


def test_main_wires_drying_then_publishing(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(weekly_rankings.drying_score, "main", Recorder(calls, "d"))
    monkeypatch.setattr(weekly_rankings.publish_rankings, "main", Recorder(calls, "p"))
    assert weekly_rankings.main(["--region", "riau"]) == EXIT_OK
    assert calls == ["d", "p"]
