import sys
from collections.abc import Callable, Sequence

from jobs import drying_score, publish_rankings
from jobs.cli import EXIT_OK, configure_logging, logger

Step = Callable[[Sequence[str] | None], int]


def run_steps(argv: Sequence[str], steps: Sequence[tuple[str, Step]]) -> int:
    for name, step in steps:
        code = step(argv)
        if code != EXIT_OK:
            logger.error(
                "weekly_rankings: %s exited %d; later steps skipped", name, code
            )
            return code
    return EXIT_OK


def main(argv: Sequence[str] | None = None) -> int:
    steps = (
        ("drying_score", drying_score.main),
        ("publish_rankings", publish_rankings.main),
    )
    return run_steps(sys.argv[1:] if argv is None else argv, steps)


if __name__ == "__main__":
    configure_logging()
    sys.exit(main())
