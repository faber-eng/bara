import argparse
import json
import os
import sys
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import TextIO

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "services" / "api"))

from domain.scenario import ScenarioError, load_scenario
from scenario_reset import ResetSummary, ScenarioResetter

EXIT_OK = 0
EXIT_FAILURE = 1
EXIT_USAGE = 2
DESCRIPTION = (
    "Reset the Riau scenario: delete the example documents (and the example cases "
    "no real user touches), seed the scenario people, contact and dams, and set the "
    "simulated clock back to zero. Real users' data is never deleted."
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="seed_scenario.py", description=DESCRIPTION)
    parser.add_argument(
        "--project", help="GCP project; else PROJECT or .secrets/bara.env"
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=REPO / "data",
        help="folder with scenario_riau.yaml (default: data/)",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="print what would change, write nothing"
    )
    parser.add_argument(
        "--json", action="store_true", help="print one JSON document on stdout"
    )
    return parser


def read_env_file(path: Path, key: str) -> str | None:
    try:
        lines = path.read_text().splitlines()
    except OSError:
        return None
    found = None
    for line in lines:
        name, separator, value = line.partition("=")
        if separator and name.strip() == key:
            found = value.strip().strip('"').strip("'")
    return found or None


def resolve_project(flag: str | None, environ: Mapping[str, str]) -> str | None:
    if flag:
        return flag
    if environ.get("PROJECT"):
        return environ["PROJECT"]
    env_file = Path(environ.get("BARA_ENV") or REPO / ".secrets" / "bara.env")
    return read_env_file(env_file, "PROJECT")


def build_resetter(project: str, data_dir: Path) -> ScenarioResetter:
    from google.cloud import firestore

    from adapters.factory import build_scenario_resetter

    scenario = load_scenario(data_dir)
    return build_scenario_resetter(firestore.Client(project=project), scenario)


def render(summary: ResetSummary, dry_run: bool, as_json: bool) -> str:
    if as_json:
        return json.dumps(
            {
                "dry_run": dry_run,
                "deleted": summary.deleted,
                "seeded": summary.seeded,
            },
            sort_keys=True,
        )
    verb = "would delete" if dry_run else "deleted"
    lines = [f"{verb} {count} {name}" for name, count in summary.deleted.items()]
    lines += [f"seeded {count} {name}" for name, count in summary.seeded.items()]
    return "\n".join(lines)


def parse(argv: list[str], err: TextIO) -> argparse.Namespace | int:
    parser = build_parser()
    if not argv:
        parser.print_help(err)
        return EXIT_USAGE
    try:
        return parser.parse_args(argv)
    except SystemExit as stop:
        return int(stop.code or 0)


def main(
    argv: list[str],
    environ: Mapping[str, str] = os.environ,
    resetter_factory: Callable[[str, Path], ScenarioResetter] = build_resetter,
    out: TextIO = sys.stdout,
    err: TextIO = sys.stderr,
) -> int:
    args = parse(argv, err)
    if isinstance(args, int):
        return args
    project = resolve_project(args.project, environ)
    if project is None:
        print(
            "no project set\npass --project <id>, set PROJECT, "
            "or put PROJECT=<id> in .secrets/bara.env",
            file=err,
        )
        return EXIT_USAGE
    return run(args, project, resetter_factory, out, err)


def run(
    args: argparse.Namespace,
    project: str,
    resetter_factory: Callable[[str, Path], ScenarioResetter],
    out: TextIO,
    err: TextIO,
) -> int:
    try:
        resetter = resetter_factory(project, args.data_dir)
        summary = resetter.plan() if args.dry_run else resetter.reset()
    except ScenarioError as error:
        print(f"{error}\ncheck data/scenario_riau.yaml and the dam file", file=err)
        return EXIT_FAILURE
    except Exception as error:
        print(
            f"failed: {type(error).__name__}: {error}\n"
            "check the project and your ADC login (gcloud auth application-default login)",
            file=err,
        )
        return EXIT_FAILURE
    print(render(summary, args.dry_run, args.json), file=out)
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
