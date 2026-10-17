import json

import pytest

from tests.public_world import NOW, WEEK, PublicWorld, walk_keys

FORBIDDEN_KEYS = {
    "name",
    "home",
    "whatsapp",
    "channels",
    "language",
    "assignee_id",
    "uploaded_by",
    "gcs_uri",
    "sha256",
    "verdict",
    "transcript",
    "transcript_en",
    "tool_calls",
    "final_json",
    "brief_id",
    "brief_en",
    "pack",
    "photos",
    "contact_id",
    "to_id",
    "model",
    "prompt_version",
    "example",
    "canal_osm_id",
}


def payloads(world: PublicWorld) -> dict[str, object]:
    queries = world.queries()
    return {
        "summary": queries.summary("riau", WEEK, NOW).model_dump(mode="json"),
        "cells": queries.cells("riau", None, 50).model_dump(mode="json"),
        "dams": [d.model_dump(mode="json") for d in queries.dams("riau")],
        "record": [r.model_dump(mode="json") for r in queries.record("riau", 50)],
        "bulletin": queries.bulletin("riau", None).model_dump(mode="json"),
    }


def leaks(text: str, blocklist: list[str]) -> list[str]:
    return [value for value in blocklist if value in text]


def forbidden_keys(node) -> set[str]:
    return set(walk_keys(node)) & FORBIDDEN_KEYS


@pytest.mark.parametrize("name", ["summary", "cells", "dams", "record", "bulletin"])
def test_no_public_payload_carries_a_private_value_or_key(name):
    world = PublicWorld()
    payload = payloads(world)[name]

    assert leaks(json.dumps(payload, ensure_ascii=False), world.blocklist()) == []
    assert forbidden_keys(payload) == set()


def test_the_world_really_holds_the_private_data_the_test_hides():
    world = PublicWorld()

    assert world.volunteers.get("uid-ari").name == "Ari Wibowo"
    assert world.volunteers.get("uid-ari").channels.whatsapp == "+6281234500001"
    assert len(world.blocklist()) > 20


def test_the_detector_flags_a_payload_built_from_a_whole_document():
    world = PublicWorld()
    whole = world.volunteers.get("uid-ari").model_dump(mode="json")

    assert leaks(json.dumps(whole), world.blocklist())
    assert forbidden_keys(whole)


def test_the_detector_flags_a_whole_evidence_document():
    world = PublicWorld()
    evidence = world.evidence.get("e-a").model_dump(mode="json")

    assert leaks(json.dumps(evidence), world.blocklist())
    assert forbidden_keys(evidence)


ROUTES = [
    "summary",
    "cells",
    "dams",
    "record",
    "bulletin",
    "export.csv",
    "export.geojson",
]


@pytest.mark.parametrize("route", ROUTES)
def test_no_public_route_carries_a_private_value(settings, route):
    world = PublicWorld()
    response = world.client(settings).get(f"/api/public/riau/{route}")

    assert response.status_code == 200
    assert leaks(response.text, world.blocklist()) == []


@pytest.mark.parametrize("route", ["summary", "cells", "dams", "record", "bulletin"])
def test_no_public_route_carries_a_private_key(settings, route):
    response = PublicWorld().client(settings).get(f"/api/public/riau/{route}")

    assert forbidden_keys(response.json()) == set()
