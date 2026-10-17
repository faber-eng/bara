import pytest

from config import ModelRoute, ModelsConfig, Settings


@pytest.fixture
def settings() -> Settings:
    return Settings(
        project="example-project",
        git_sha="abc1234",
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
