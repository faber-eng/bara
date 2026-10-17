import json
from dataclasses import dataclass
from pathlib import Path

import yaml
from pydantic import AwareDatetime, ValidationError

from contracts import Contact, Contract, Dam, GeoPoint, Volunteer

SCENARIO_FILE = "scenario_riau.yaml"


class ScenarioError(Exception):
    pass


class EvidenceFixture(Contract):
    id: str
    kind: str
    path: str
    expect: dict[str, str]


class ScenarioSpec(Contract):
    region: str
    sim_start: AwareDatetime
    dams_file: str
    volunteers: list[Volunteer]
    contacts: list[Contact]
    evidence_fixtures: list[EvidenceFixture]


@dataclass(frozen=True)
class Scenario:
    spec: ScenarioSpec
    dams: list[Dam]

    @property
    def people_ids(self) -> list[str]:
        return [item.id for item in (*self.spec.volunteers, *self.spec.contacts)]


def dam_from_feature(feature: dict) -> Dam:
    longitude, latitude = feature["geometry"]["coordinates"]
    return Dam.model_validate(
        {**feature["properties"], "point": GeoPoint(lat=latitude, lon=longitude)}
    )


def read_dams(path: Path) -> list[Dam]:
    try:
        collection = json.loads(path.read_text())
        return [dam_from_feature(feature) for feature in collection["features"]]
    except (OSError, ValueError, KeyError, ValidationError) as error:
        raise ScenarioError(f"cannot read dams from {path}: {error}") from error


def read_spec(path: Path) -> ScenarioSpec:
    try:
        return ScenarioSpec.model_validate(yaml.safe_load(path.read_text()))
    except (OSError, yaml.YAMLError, ValidationError) as error:
        raise ScenarioError(f"cannot read scenario {path}: {error}") from error


def duplicates(ids: list[str]) -> list[str]:
    return sorted({item for item in ids if ids.count(item) > 1})


def check_scenario(scenario: Scenario) -> None:
    repeated = duplicates(scenario.people_ids) + duplicates(
        [dam.id for dam in scenario.dams]
    )
    if repeated:
        raise ScenarioError(f"duplicate ids in the scenario: {repeated}")
    seeded = [*scenario.spec.volunteers, *scenario.spec.contacts, *scenario.dams]
    real = [item.id for item in seeded if not item.example]
    if real:
        raise ScenarioError(f"scenario documents must be example: true, got {real}")


def load_scenario(directory: Path) -> Scenario:
    spec = read_spec(directory / SCENARIO_FILE)
    scenario = Scenario(spec, read_dams(directory / spec.dams_file))
    check_scenario(scenario)
    return scenario
