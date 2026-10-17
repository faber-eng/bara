from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
REPO_CONFIG_DIR = REPO / "config"


@pytest.fixture
def config_dir() -> Path:
    return REPO_CONFIG_DIR
