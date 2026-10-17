import os

import pytest

from config import JudgeMode, ModelRoute, ModelsConfig, Settings


@pytest.fixture
def settings() -> Settings:
    return Settings(
        project="example-project",
        git_sha="abc1234",
        judge_mode=JudgeMode(enabled=False, max_resets_per_hour=20),
        region="asia-southeast1",
        api_url="https://api.example.test",
        models=ModelsConfig(
            reasoning=ModelRoute(
                model="reasoning-primary",
                location="global",
                fallback="reasoning-backup",
            ),
            fast=ModelRoute(
                model="fast-primary", location="global", fallback="fast-backup"
            ),
        ),
    )


def pytest_collection_modifyitems(config, items):
    if os.environ.get("BARA_LIVE") == "1":
        return
    skip_live = pytest.mark.skip(reason="live test: set BARA_LIVE=1 to run")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip_live)
