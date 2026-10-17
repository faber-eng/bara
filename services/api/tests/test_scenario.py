import csv
import json
from pathlib import Path

import pytest
import yaml

from domain.scenario import ScenarioError, load_scenario

DATA = Path(__file__).resolve().parents[3] / "data"
WEB_PEOPLE = Path(__file__).resolve().parents[3] / "apps/web/src/lib/judge/people.ts"


@pytest.fixture(scope="module")
def scenario():
    return load_scenario(DATA)


def test_the_scenario_has_ten_volunteers_by_role_and_one_contact(scenario):
    roles = [volunteer.role for volunteer in scenario.spec.volunteers]

    assert roles.count("volunteer") == 6
    assert roles.count("repair_team") == 2
    assert roles.count("patrol") == 2
    assert [c.name for c in scenario.spec.contacts] == [
        "Manggala Agni Daops Pekanbaru (example)"
    ]


def test_the_ids_the_judge_bar_uses_exist(scenario):
    web = WEB_PEOPLE.read_text()
    bar_ids = ["vol-ari", "team-sari", "vol-dedi", "contact-daops-pekanbaru"]

    assert all(f'"{item}"' in web for item in bar_ids)
    assert set(bar_ids) <= set(scenario.people_ids)


def test_every_seeded_document_is_example_data(scenario):
    everything = [*scenario.spec.volunteers, *scenario.spec.contacts, *scenario.dams]

    assert all(item.example for item in everything)


def test_the_forty_dams_come_from_the_dam_file_with_their_states(scenario):
    assert len(scenario.dams) == 40
    broken = {dam.id for dam in scenario.dams if dam.last_state == "broken"}
    assert "dam-riau-009" in broken
    first = scenario.dams[0]
    assert (first.point.lat, first.point.lon) == (0.464992, 101.950328)


def test_every_home_is_inside_the_area_of_interest(scenario):
    for volunteer in scenario.spec.volunteers:
        assert 0.35 <= volunteer.home.lat <= 0.85
        assert 101.95 <= volunteer.home.lon <= 102.55


def test_evidence_fixtures_point_at_existing_eval_files_marked_scenario(scenario):
    with (DATA / "eval/labels.csv").open() as handle:
        marked = {
            row["object_path"]
            for row in csv.DictReader(handle)
            if row["notes"].startswith("scenario")
        }

    paths = {fixture.path for fixture in scenario.spec.evidence_fixtures}

    assert paths == marked
    assert all((DATA / "eval" / path).is_file() for path in paths)


def write_scenario(tmp_path, mutate=lambda spec: None):
    spec = yaml.safe_load((DATA / "scenario_riau.yaml").read_text())
    mutate(spec)
    (tmp_path / "scenario_riau.yaml").write_text(yaml.safe_dump(spec))
    (tmp_path / "dams_riau_sample.geojson").write_text(
        (DATA / "dams_riau_sample.geojson").read_text()
    )
    return tmp_path


def test_a_duplicate_person_id_is_refused(tmp_path):
    def duplicate(spec):
        spec["volunteers"].append(dict(spec["volunteers"][0]))

    with pytest.raises(ScenarioError, match="vol-ari"):
        load_scenario(write_scenario(tmp_path, duplicate))


def test_a_non_example_person_is_refused(tmp_path):
    def real(spec):
        spec["volunteers"][0]["example"] = False

    with pytest.raises(ScenarioError, match="example"):
        load_scenario(write_scenario(tmp_path, real))


def test_an_unknown_field_is_refused(tmp_path):
    def extra(spec):
        spec["volunteers"][0]["nickname"] = "x"

    with pytest.raises(ScenarioError):
        load_scenario(write_scenario(tmp_path, extra))


def test_a_missing_file_is_a_scenario_error(tmp_path):
    with pytest.raises(ScenarioError):
        load_scenario(tmp_path)


def test_a_broken_dam_file_is_a_scenario_error(tmp_path):
    directory = write_scenario(tmp_path)
    (directory / "dams_riau_sample.geojson").write_text(json.dumps({"features": [{}]}))

    with pytest.raises(ScenarioError):
        load_scenario(directory)
