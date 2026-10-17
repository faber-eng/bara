import json
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import yaml
from pydantic import AwareDatetime, ValidationError

from contracts import Contact, Contract, Dam, GeoPoint, QuietCell, Volunteer

SCENARIO_FILE = "scenario_riau.yaml"
QUIET_AFTER_SIM_DAYS = timedelta(days=10)
FIRE_CELLS = 3


class ScenarioError(Exception):
    pass


class EvidenceFixture(Contract):
    id: str
    kind: str
    path: str
    expect: dict[str, str]


class ScenarioFireEvent(Contract):
    event_id: str
    source: str
    start_date: date
    quiet_date: date
    cells: list[QuietCell]


class ScenarioSpec(Contract):
    region: str
    sim_start: AwareDatetime
    dams_file: str
    volunteers: list[Volunteer]
    contacts: list[Contact]
    evidence_fixtures: list[EvidenceFixture]
    fire_event: ScenarioFireEvent


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


def check_fire_event(spec: ScenarioSpec) -> None:
    fire = spec.fire_event
    sim_day = spec.sim_start.date()
    if fire.quiet_date != sim_day + QUIET_AFTER_SIM_DAYS:
        raise ScenarioError(
            f"fire quiet_date must be sim day 10 ({sim_day + QUIET_AFTER_SIM_DAYS})"
        )
    if len(fire.cells) != FIRE_CELLS:
        raise ScenarioError(f"fire_event needs {FIRE_CELLS} cells")
    repeated = duplicates([cell.cell_id for cell in fire.cells])
    if repeated:
        raise ScenarioError(f"duplicate fire cells: {repeated}")


def load_scenario(directory: Path) -> Scenario:
    spec = read_spec(directory / SCENARIO_FILE)
    scenario = Scenario(spec, read_dams(directory / spec.dams_file))
    check_scenario(scenario)
    check_fire_event(spec)
    return scenario
