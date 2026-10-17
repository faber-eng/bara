import os
from collections.abc import Mapping
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

Role = Literal["reasoning", "fast"]

MODEL_OVERRIDES: dict[Role, str] = {
    "reasoning": "REASONING_MODEL",
    "fast": "FAST_MODEL",
}


DEFAULT_REGION = "asia-southeast1"
JUDGE_MODE_VARIABLE = "BARA_JUDGE_MODE"


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


class JudgeMode(Config):
    enabled: bool
    max_resets_per_hour: int


class AgentConfig(Config):
    max_llm_calls: int = Field(ge=1)
    max_cases_per_trigger: int = Field(ge=1)


class AppConfig(Config):
    model_config = ConfigDict(extra="ignore", frozen=True)

    grid_cell_m: int = Field(gt=0)
    judge_mode: JudgeMode
    agent: AgentConfig


class Settings(Config):
    project: str
    git_sha: str
    models: ModelsConfig
    judge_mode: JudgeMode
    agent: AgentConfig
    grid_cell_m: int
    region: str
    api_url: str | None
    config_dir: Path
    samples_dir: Path
    scenario_dir: Path

    @property
    def evidence_bucket(self) -> str:
        return f"{self.project}-bara-evidence"

    @property
    def tasks_invoker_email(self) -> str:
        return f"bara-tasks-invoker@{self.project}.iam.gserviceaccount.com"


def load_settings(
    environ: Mapping[str, str] = os.environ, config_dir: Path | None = None
) -> Settings:
    directory = resolve_config_dir(environ, config_dir)
    models = apply_model_overrides(read_models(directory / "models.yaml"), environ)
    app = read_app(directory / "app.yaml")
    return Settings(
        project=require_project(environ),
        git_sha=read_git_sha(environ),
        models=models,
        judge_mode=apply_judge_override(app.judge_mode, environ),
        agent=app.agent,
        grid_cell_m=app.grid_cell_m,
        region=read_optional(environ, "REGION") or DEFAULT_REGION,
        api_url=read_optional(environ, "BARA_API_URL"),
        config_dir=directory,
        samples_dir=resolve_samples_dir(environ),
        scenario_dir=resolve_scenario_dir(environ),
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


def resolve_samples_dir(environ: Mapping[str, str]) -> Path:
    from_env = read_optional(environ, "BARA_SAMPLES_DIR")
    if from_env is not None:
        return Path(from_env)
    parents = Path(__file__).resolve().parents
    if len(parents) < 3:
        raise ConfigError(
            "BARA_SAMPLES_DIR is not set and no repo data/samples sits above this file"
        )
    return parents[2] / "data" / "samples"


def resolve_scenario_dir(environ: Mapping[str, str]) -> Path:
    from_env = read_optional(environ, "BARA_SCENARIO_DIR")
    if from_env is not None:
        return Path(from_env)
    parents = Path(__file__).resolve().parents
    if len(parents) < 3:
        raise ConfigError(
            "BARA_SCENARIO_DIR is not set and no repo data/ sits above this file"
        )
    return parents[2] / "data"


def full_flow_region(config_dir: Path) -> str:
    path = config_dir / "regions.yaml"
    regions = read_yaml(path)
    if not isinstance(regions, dict):
        raise ConfigError(f"{path} is not a mapping of regions")
    full = [
        region_id
        for region_id, entry in regions.items()
        if isinstance(entry, dict) and entry.get("full_flow") is True
    ]
    if len(full) != 1:
        raise ConfigError(f"{path} must mark exactly one region full_flow: true")
    return full[0]


def read_yaml(path: Path) -> object:
    try:
        return yaml.safe_load(path.read_text())
    except OSError as error:
        raise ConfigError(f"cannot read {path}: {error}") from error
    except yaml.YAMLError as error:
        raise ConfigError(f"{path} is not valid YAML: {error}") from error


def read_models(path: Path) -> ModelsConfig:
    document = read_yaml(path)
    try:
        return ModelsConfig.model_validate(document)
    except ValidationError as error:
        raise ConfigError(
            f"{path} does not match the models config: {error}"
        ) from error


def read_app(path: Path) -> AppConfig:
    document = read_yaml(path)
    try:
        return AppConfig.model_validate(document)
    except ValidationError as error:
        raise ConfigError(f"{path} does not match the app config: {error}") from error


def apply_judge_override(
    judge_mode: JudgeMode, environ: Mapping[str, str]
) -> JudgeMode:
    if JUDGE_MODE_VARIABLE not in environ:
        return judge_mode
    value = environ[JUDGE_MODE_VARIABLE].strip()
    if value not in ("0", "1"):
        raise ConfigError(f"{JUDGE_MODE_VARIABLE} must be 0 or 1, got {value!r}")
    return judge_mode.model_copy(update={"enabled": value == "1"})


def read_optional(environ: Mapping[str, str], name: str) -> str | None:
    value = environ.get(name, "").strip()
    if value == "":
        return None
    return value


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
