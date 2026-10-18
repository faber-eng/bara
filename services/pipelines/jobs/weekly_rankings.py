import argparse
import os
import sys
from collections.abc import Mapping, Sequence

from ee_lib.config import ConfigError, UnknownRegion, load_region_ids
from jobs import drying_score, publish_rankings
from jobs.cli import (
    EXIT_FAILURE,
    EXIT_OK,
    EXIT_USAGE,
    configure_logging,
    logger,
    resolve_config_dir,
    run_steps,
)


def parse_args(argv: Sequence[str]) -> tuple[argparse.Namespace, list[str]]:
    parser = argparse.ArgumentParser(
        prog="python -m jobs.weekly_rankings",
        description="Score and publish one week for every region in "
        "config/regions.yaml, or for the regions named with --region. "
        "Other flags go to both steps. One region failing does not stop the "
        "others; the exit code is non-zero if any failed.",
        allow_abbrev=False,
    )
    parser.add_argument("--region", action="append", default=[])
    parser.add_argument("--config-dir")
    return parser.parse_known_args(argv)


def region_ids(
    requested: Sequence[str], config_dir: str | None, environ: Mapping[str, str]
) -> list[str]:
    known = load_region_ids(resolve_config_dir(config_dir, environ))
    unknown = [region for region in requested if region not in known]
    if unknown:
        raise UnknownRegion(f"regions not in config/regions.yaml: {', '.join(unknown)}")
    return list(requested) if requested else known


def region_argv(rest: Sequence[str], config_dir: str | None, region: str) -> list[str]:
    config_flags = ["--config-dir", config_dir] if config_dir else []
    return [*rest, *config_flags, "--region", region]


def main(
    argv: Sequence[str] | None = None, environ: Mapping[str, str] = os.environ
) -> int:
    args, rest = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        regions = region_ids(args.region, args.config_dir, environ)
    except (UnknownRegion, ConfigError) as error:
        print(f"error: {error}", file=sys.stderr)
        return EXIT_USAGE if isinstance(error, UnknownRegion) else EXIT_FAILURE
    steps = (
        ("drying_score", drying_score.main),
        ("publish_rankings", publish_rankings.main),
    )
    failed = []
    for region in regions:
        code = run_steps(
            "weekly_rankings", region_argv(rest, args.config_dir, region), steps
        )
        if code != EXIT_OK:
            failed.append(region)
    if failed:
        logger.error("weekly_rankings: failed regions: %s", ", ".join(failed))
        return EXIT_FAILURE
    return EXIT_OK


if __name__ == "__main__":
    configure_logging()
    sys.exit(main())
