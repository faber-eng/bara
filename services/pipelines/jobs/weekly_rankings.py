import sys
from collections.abc import Sequence

from jobs import drying_score, publish_rankings
from jobs.cli import configure_logging, run_steps


def main(argv: Sequence[str] | None = None) -> int:
    steps = (
        ("drying_score", drying_score.main),
        ("publish_rankings", publish_rankings.main),
    )
    return run_steps("weekly_rankings", sys.argv[1:] if argv is None else argv, steps)


if __name__ == "__main__":
    configure_logging()
    sys.exit(main())
