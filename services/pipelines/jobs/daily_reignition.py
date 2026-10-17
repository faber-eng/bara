import sys
from collections.abc import Sequence

from jobs import fire_events, reignition_features, score_reignition
from jobs.cli import configure_logging, run_steps


def main(argv: Sequence[str] | None = None) -> int:
    steps = (
        ("fire_events", fire_events.main),
        ("reignition_features", reignition_features.main),
        ("score_reignition", score_reignition.main),
    )
    return run_steps("daily_reignition", sys.argv[1:] if argv is None else argv, steps)


if __name__ == "__main__":
    configure_logging()
    sys.exit(main())
