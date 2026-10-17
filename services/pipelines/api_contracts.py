import importlib.util
import os
import sys
from pathlib import Path
from types import ModuleType

DEFAULT_PATH = Path(__file__).resolve().parents[1] / "api" / "contracts.py"
MODULE_NAME = "bara_api_contracts"


def load_api_contracts() -> ModuleType:
    if MODULE_NAME in sys.modules:
        return sys.modules[MODULE_NAME]
    path = Path(os.environ.get("BARA_CONTRACTS_PATH") or DEFAULT_PATH)
    spec = importlib.util.spec_from_file_location(MODULE_NAME, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load the API contracts from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[MODULE_NAME] = module
    spec.loader.exec_module(module)
    return module


contracts = load_api_contracts()
