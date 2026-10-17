import json
import logging
import sys
from collections.abc import Callable, Mapping
from pathlib import Path

from ee_lib.config import ConfigError, UnknownRegion

EXIT_OK = 0
EXIT_FAILURE = 1
EXIT_USAGE = 2
DATASET = "bara"

logger = logging.getLogger("bara.jobs")


class JobError(Exception):
    pass


class UsageError(Exception):
    pass


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


def emit(summary: Mapping[str, object]) -> None:
    sys.stdout.write(json.dumps(summary, default=str) + "\n")


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
