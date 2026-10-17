import csv
import logging
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import main
from adapters.gemini import ModelGateway
from adapters.samples import SampleLibrary
from tests.fakes import FakeModels, FakeVerifier

REPO = Path(__file__).resolve().parents[3]
REAL_SAMPLES = REPO / "data" / "samples"

HEADER = "| file | label | author | licence | source |\n|---|---|---|---|---|\n"


def row(file, label="Label", author="Ann", licence="CC BY 4.0", source="team"):
    return f"| {file} | {label} | {author} | {licence} | {source} |\n"


def write_library(root: Path, rows: list[str], files: list[str]) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "CREDITS.md").write_text("# Sample credits\n\n" + HEADER + "".join(rows))
    for name in files:
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"data-" + name.encode())
    return root


def make_client(settings, samples_dir):
    configured = settings.model_copy(update={"samples_dir": samples_dir})
    gateway = ModelGateway(
        configured.models, {"reasoning": FakeModels([]), "fast": FakeModels([])}
    )
    return TestClient(main.build_app(configured, gateway, FakeVerifier({})))


@pytest.fixture
def library(tmp_path):
    return write_library(
        tmp_path / "samples",
        [
            row("photo/broken-dam-1.jpg", "Breached dam", "Peter Bond", "CC BY-SA 2.0"),
            row("voice/leak.ogg", "Leak note"),
            row("area/riau-area-1.geojson", "Riau area 1"),
        ],
        ["photo/broken-dam-1.jpg", "voice/leak.ogg", "area/riau-area-1.geojson"],
    )


def test_the_listing_has_id_kind_label_credit_and_url(settings, library):
    client = make_client(settings, library)

    response = client.get("/api/samples")

    assert response.status_code == 200
    assert {item["id"]: item for item in response.json()}["broken-dam-1"] == {
        "id": "broken-dam-1",
        "kind": "photo",
        "label": "Breached dam",
        "credit": "Peter Bond, CC BY-SA 2.0",
        "url": "/api/samples/broken-dam-1/file",
    }


def test_the_kind_filter_narrows_the_listing(settings, library):
    client = make_client(settings, library)

    response = client.get("/api/samples", params={"kind": "voice"})

    assert [item["id"] for item in response.json()] == ["leak"]


def test_a_bogus_kind_is_422(settings, library):
    client = make_client(settings, library)

    assert client.get("/api/samples", params={"kind": "video"}).status_code == 422


def test_a_missing_directory_lists_nothing(settings, tmp_path):
    client = make_client(settings, tmp_path / "absent")

    response = client.get("/api/samples")

    assert response.status_code == 200
    assert response.json() == []


def test_an_empty_directory_lists_nothing(settings, tmp_path):
    (tmp_path / "samples").mkdir()
    client = make_client(settings, tmp_path / "samples")

    assert client.get("/api/samples").json() == []


def test_a_file_with_no_credits_row_is_skipped_and_logged(settings, library, caplog):
    (library / "photo" / "orphan.jpg").write_bytes(b"x")
    client = make_client(settings, library)

    with caplog.at_level(logging.WARNING):
        ids = [item["id"] for item in client.get("/api/samples").json()]

    assert "orphan" not in ids
    assert "orphan.jpg" in caplog.text


def test_a_row_with_no_file_is_skipped_and_logged(settings, library, caplog):
    with (library / "CREDITS.md").open("a") as handle:
        handle.write(row("photo/ghost.jpg"))
    client = make_client(settings, library)

    with caplog.at_level(logging.WARNING):
        ids = [item["id"] for item in client.get("/api/samples").json()]

    assert "ghost" not in ids
    assert "ghost.jpg" in caplog.text


def test_a_row_for_an_unknown_kind_folder_is_skipped(settings, library):
    write_library(
        library,
        [row("photo/broken-dam-1.jpg"), row("video/clip.mp4")],
        ["photo/broken-dam-1.jpg", "video/clip.mp4"],
    )
    client = make_client(settings, library)

    assert [item["id"] for item in client.get("/api/samples").json()] == [
        "broken-dam-1"
    ]


def test_a_row_that_escapes_the_directory_is_skipped(settings, library, tmp_path):
    (tmp_path / "secret.jpg").write_bytes(b"x")
    with (library / "CREDITS.md").open("a") as handle:
        handle.write(row("photo/../../secret.jpg"))
    client = make_client(settings, library)

    ids = [item["id"] for item in client.get("/api/samples").json()]

    assert "secret" not in ids


def test_the_file_route_serves_the_bytes(settings, library):
    client = make_client(settings, library)

    response = client.get("/api/samples/broken-dam-1/file")

    assert response.status_code == 200
    assert response.content == b"data-photo/broken-dam-1.jpg"
    assert response.headers["content-type"].startswith("image/jpeg")


def test_the_file_route_types_geojson_and_ogg(settings, library):
    client = make_client(settings, library)

    assert (
        client.get("/api/samples/riau-area-1/file")
        .headers["content-type"]
        .startswith("application/geo+json")
    )
    assert (
        client.get("/api/samples/leak/file")
        .headers["content-type"]
        .startswith("audio/ogg")
    )


def test_an_unknown_id_is_404(settings, library):
    client = make_client(settings, library)

    assert client.get("/api/samples/nope/file").status_code == 404


@pytest.mark.parametrize(
    "path",
    [
        "..%2F..%2Fsecret.jpg",
        "%2e%2e%2fCREDITS.md",
        "photo%2Fbroken-dam-1.jpg",
        "CREDITS.md",
    ],
)
def test_traversal_and_paths_are_404(settings, library, path):
    client = make_client(settings, library)

    assert client.get(f"/api/samples/{path}/file").status_code == 404


def test_the_library_lists_in_a_stable_order(library):
    items = [sample.item.id for sample in SampleLibrary(library).list()]

    assert items == sorted(items)


def real_items():
    return SampleLibrary(REAL_SAMPLES).list()


def credit_files():
    lines = (REAL_SAMPLES / "CREDITS.md").read_text().splitlines()
    cells = [[c.strip() for c in line.strip("|").split("|")] for line in lines]
    return [c[0] for c in cells if len(c) == 5 and "/" in c[0]]


def test_every_real_sample_file_has_a_credits_row_and_back():
    on_disk = {
        str(path.relative_to(REAL_SAMPLES))
        for path in REAL_SAMPLES.rglob("*")
        if path.is_file() and path.name not in {"CREDITS.md", ".gitkeep"}
    }

    assert on_disk == set(credit_files())


def test_the_real_listing_has_twelve_unique_items():
    ids = [sample.item.id for sample in real_items()]

    assert len(ids) == 12
    assert len(set(ids)) == 12


def test_no_real_sample_is_an_eval_photo():
    with (REPO / "data" / "eval" / "labels.csv").open() as handle:
        eval_files = {Path(record["file"]).stem for record in csv.DictReader(handle)}
    eval_files |= {Path(f).name for f in eval_files}

    names = {Path(file).name for file in credit_files()}
    stems = {Path(file).stem for file in credit_files()}

    assert not (names | stems) & eval_files
