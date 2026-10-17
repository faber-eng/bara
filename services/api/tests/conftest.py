import os
from pathlib import Path

import pytest

from config import (
    AgentConfig,
    JudgeMode,
    ModelRoute,
    ModelsConfig,
    Settings,
    TasksConfig,
)


@pytest.fixture
def settings() -> Settings:
    return Settings(
        project="example-project",
        git_sha="abc1234",
        judge_mode=JudgeMode(enabled=False, max_resets_per_hour=20),
        agent=AgentConfig(max_llm_calls=12, max_cases_per_trigger=3),
        tasks=TasksConfig(
            default_deadline_hours={
                "dam_check": 72,
                "dam_repair": 168,
                "patrol_recheck": 24,
            },
            human_review_confidence=0.7,
            location_tolerance_m=300,
        ),
        default_language="id",
        grid_cell_m=1000,
        region="asia-southeast1",
        api_url="https://api.example.test",
        config_dir=Path(__file__).resolve().parents[3] / "config",
        samples_dir=Path(__file__).resolve().parents[3] / "data" / "samples",
        scenario_dir=Path(__file__).resolve().parents[3] / "data",
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
