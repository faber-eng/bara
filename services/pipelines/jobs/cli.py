import json
import logging
import sys
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

from adapters.bigquery import QueryResult
from ee_lib.config import ConfigError, RegionConfig, UnknownRegion

EXIT_OK = 0
EXIT_FAILURE = 1
EXIT_USAGE = 2
DATASET = "bara"

logger = logging.getLogger("bara.jobs")

Step = Callable[[Sequence[str] | None], int]


class JobError(Exception):
    pass


class UsageError(Exception):
    pass


def full_flow_region(region: RegionConfig) -> str:
    if not region.full_flow:
        raise UsageError(
            f"region {region.id!r} is not full_flow in config/regions.yaml; "
            "the reignition model serves the full-flow region only"
        )
    return region.id


def configure_logging() -> None:
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("%(message)s"))
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)


def resolve_project(flag: str | None, environ: Mapping[str, str]) -> str:
    project = flag or environ.get("GOOGLE_CLOUD_PROJECT", "").strip()
    if project == "":
        raise UsageError("no project: pass --project or set GOOGLE_CLOUD_PROJECT")
    return project


def resolve_config_dir(flag: str | None, environ: Mapping[str, str]) -> Path:
    if flag:
        return Path(flag)
    from_env = environ.get("BARA_CONFIG_DIR", "").strip()
    if from_env != "":
        return Path(from_env)
    return Path(__file__).resolve().parents[3] / "config"


def resolve_data_dir(flag: str | None, environ: Mapping[str, str]) -> Path:
    if flag:
        return Path(flag)
    from_env = environ.get("BARA_DATA_DIR", "").strip()
    if from_env != "":
        return Path(from_env)
    return Path(__file__).resolve().parents[3] / "data"


def write_json_atomic(path: Path, document: object) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n")
    temporary.replace(path)


def emit(summary: Mapping[str, object]) -> None:
    sys.stdout.write(json.dumps(summary, default=str) + "\n")


def query_report(step: str, result: QueryResult) -> dict[str, object]:
    logger.info("%s: %s bytes billed", step, result.bytes_billed)
    return {"step": step, "bytes": result.bytes_billed, "estimate": result.dry_run}


def run_job(work: Callable[[], Mapping[str, object]]) -> int:
    try:
        emit(work())
    except (UsageError, UnknownRegion) as error:
        print(f"error: {error}", file=sys.stderr)
        return EXIT_USAGE
    except (JobError, ConfigError) as error:
        print(f"error: {error}", file=sys.stderr)
        return EXIT_FAILURE
    return EXIT_OK


def run_steps(job: str, argv: Sequence[str], steps: Sequence[tuple[str, Step]]) -> int:
    for name, step in steps:
        code = step(argv)
        if code != EXIT_OK:
            logger.error("%s: %s exited %d; later steps skipped", job, name, code)
            return code
    return EXIT_OK
