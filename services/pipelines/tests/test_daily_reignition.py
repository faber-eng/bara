from jobs import daily_reignition
from jobs.cli import EXIT_FAILURE, EXIT_OK


def recorder(calls, name, code=EXIT_OK):
    def step(argv):
        calls.append((name, list(argv)))
        return code

    return step


def test_runs_fire_events_then_features_then_scoring(monkeypatch):
    calls = []
    monkeypatch.setattr(daily_reignition.fire_events, "main", recorder(calls, "f"))
    monkeypatch.setattr(
        daily_reignition.reignition_features, "main", recorder(calls, "r")
    )
    monkeypatch.setattr(daily_reignition.score_reignition, "main", recorder(calls, "s"))

    assert daily_reignition.main(["--region", "riau"]) == EXIT_OK
    assert calls == [
        ("f", ["--region", "riau"]),
        ("r", ["--region", "riau"]),
        ("s", ["--region", "riau"]),
    ]


def test_a_failed_step_skips_the_rest(monkeypatch):
    calls = []
    monkeypatch.setattr(
        daily_reignition.fire_events, "main", recorder(calls, "f", EXIT_FAILURE)
    )
    monkeypatch.setattr(
        daily_reignition.reignition_features, "main", recorder(calls, "r")
    )
    monkeypatch.setattr(daily_reignition.score_reignition, "main", recorder(calls, "s"))

    assert daily_reignition.main(["--region", "riau"]) == EXIT_FAILURE
    assert [name for name, _ in calls] == ["f"]
