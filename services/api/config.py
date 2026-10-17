import os
from collections.abc import Mapping
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError

Role = Literal["reasoning", "fast"]

MODEL_OVERRIDES: dict[Role, str] = {
    "reasoning": "REASONING_MODEL",
    "fast": "FAST_MODEL",
}


class ConfigError(Exception):
    pass


class Config(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ModelRoute(Config):
    model: str
    location: str
    fallback: str


class ModelsConfig(Config):
    reasoning: ModelRoute
    fast: ModelRoute

    def for_role(self, role: Role) -> ModelRoute:
        if role == "reasoning":
            return self.reasoning
        return self.fast


class Settings(Config):
    project: str
    git_sha: str
    models: ModelsConfig


def load_settings(
    environ: Mapping[str, str] = os.environ, config_dir: Path | None = None
) -> Settings:
    directory = resolve_config_dir(environ, config_dir)
    models = apply_model_overrides(read_models(directory / "models.yaml"), environ)
    return Settings(
        project=require_project(environ), git_sha=read_git_sha(environ), models=models
    )


def resolve_config_dir(environ: Mapping[str, str], config_dir: Path | None) -> Path:
    if config_dir is not None:
        return config_dir
    from_env = environ.get("BARA_CONFIG_DIR", "").strip()
    if from_env != "":
        return Path(from_env)
    parents = Path(__file__).resolve().parents
    if len(parents) < 3:
        raise ConfigError(
            "BARA_CONFIG_DIR is not set and no repo config/ sits above this file"
        )
    return parents[2] / "config"


def read_models(path: Path) -> ModelsConfig:
    try:
        document = yaml.safe_load(path.read_text())
    except OSError as error:
        raise ConfigError(f"cannot read {path}: {error}") from error
    except yaml.YAMLError as error:
        raise ConfigError(f"{path} is not valid YAML: {error}") from error
    try:
        return ModelsConfig.model_validate(document)
    except ValidationError as error:
        raise ConfigError(
            f"{path} does not match the models config: {error}"
        ) from error


def apply_model_overrides(
    models: ModelsConfig, environ: Mapping[str, str]
) -> ModelsConfig:
    routes = {role: models.for_role(role) for role in MODEL_OVERRIDES}
    for role, variable in MODEL_OVERRIDES.items():
        if variable not in environ:
            continue
        override = environ[variable].strip()
        if override == "":
            raise ConfigError(
                f"{variable} is set but empty; unset it or give a model ID"
            )
        routes[role] = routes[role].model_copy(update={"model": override})
    return ModelsConfig(reasoning=routes["reasoning"], fast=routes["fast"])


def require_project(environ: Mapping[str, str]) -> str:
    project = environ.get("GOOGLE_CLOUD_PROJECT", "").strip()
    if project == "":
        raise ConfigError("GOOGLE_CLOUD_PROJECT is not set")
    return project


def read_git_sha(environ: Mapping[str, str]) -> str:
    git_sha = environ.get("GIT_SHA", "").strip()
    if git_sha == "":
        return "unknown"
    return git_sha
