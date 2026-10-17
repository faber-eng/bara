import importlib.util
import sys
from pathlib import Path
from types import ModuleType

CONTRACTS_PATH = Path(__file__).resolve().parents[2] / "api" / "contracts.py"


def load_api_contracts() -> ModuleType:
    name = "bara_api_contracts"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, CONTRACTS_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {CONTRACTS_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module
