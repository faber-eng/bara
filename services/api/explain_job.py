import argparse
import asyncio
import json
import sys
from collections.abc import Sequence
from dataclasses import asdict

from adapters.factory import build_adapters
from adapters.gemini import ModelGateway, build_vertex_clients
from config import load_settings
from logs import configure_logging
from main import build_explanation_precomputer


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python explain_job.py")
    parser.add_argument("--region", required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str]) -> int:
    configure_logging()
    args = parse_args(argv)
    settings = load_settings()
    gateway = ModelGateway(settings.models, build_vertex_clients(settings))
    precomputer = build_explanation_precomputer(
        settings, build_adapters(settings), gateway
    )
    result = asyncio.run(precomputer.run(args.region))
    print(json.dumps(asdict(result), indent=2))
    return 0 if result.failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
