import pytest

from domain.evidence_eval import (
    FIELDS,
    LabelRow,
    ScoredItem,
    accuracy_by_field,
    confusion,
    evidence_row,
    kind_for,
    nearest_rank,
    parse_label_row,
    summarize_set,
    task_type_for,
)


def label(file="a.jpg", **values):
    fields = {
        "subject": "canal_dam",
        "dam_state": "broken",
        "smoke": "none",
        "hot_ground_signs": "none",
        "open_flame": "no",
    }
    fields.update(values)
    return LabelRow(file=file, object_path=f"photos/{file}", labels=fields)


def scored(row, verdict=None, latency_ms=1000.0, error=None):
    return ScoredItem(row=row, verdict=verdict, latency_ms=latency_ms, error=error)


def test_kind_follows_the_file_suffix():
    assert kind_for("photos/a.jpg") == "photo"
    assert kind_for("voice/v.ogg") == "audio"
    with pytest.raises(ValueError):
        kind_for("notes.txt")


def test_task_type_follows_the_labelled_subject():
    assert task_type_for("canal_dam") == "dam_check"
    assert task_type_for("burned_peat") == "patrol_recheck"
    assert task_type_for("smoke_scene") == "patrol_recheck"


def test_nearest_rank_percentile():
    values = [float(v) for v in range(1, 21)]
    assert nearest_rank(values, 0.5) == 10.0
    assert nearest_rank(values, 0.95) == 19.0
    assert nearest_rank([7.0], 0.95) == 7.0
    assert nearest_rank([], 0.5) is None


def test_accuracy_counts_a_failed_read_as_wrong_and_skips_unknown_labels():
    right = label("a.jpg")
    wrong = label("b.jpg")
    unknown = label("c.jpg", hot_ground_signs="unknown")
    items = [
        scored(right, verdict=dict(right.labels)),
        scored(wrong, verdict={**wrong.labels, "dam_state": "intact"}),
        scored(unknown, verdict=dict(unknown.labels)),
        scored(label("d.jpg"), error="the model call failed: 500"),
    ]

    by_field = {row["field"]: row for row in accuracy_by_field(items)}

    assert list(by_field) == list(FIELDS)
    assert by_field["dam_state"] == {
        "field": "dam_state",
        "correct": 2,
        "n": 4,
        "accuracy": 0.5,
    }
    assert by_field["hot_ground_signs"]["n"] == 3
    assert by_field["hot_ground_signs"]["correct"] == 2


def test_confusion_rows_are_labels_and_columns_are_verdicts():
    a = label("a.jpg", dam_state="broken")
    b = label("b.jpg", dam_state="broken")
    c = label("c.jpg", dam_state="intact")
    items = [
        scored(a, verdict={**a.labels, "dam_state": "broken"}),
        scored(b, verdict={**b.labels, "dam_state": "intact"}),
        scored(c, verdict={**c.labels, "dam_state": "intact"}),
        scored(label("d.jpg", dam_state="intact"), error="boom"),
    ]

    matrix = confusion(items, "dam_state")

    assert matrix == {
        "field": "dam_state",
        "labels": ["broken", "failed", "intact"],
        "matrix": [[1, 0, 1], [0, 0, 0], [0, 1, 1]],
    }


def test_summarize_set_reports_latency_of_successful_reads_only():
    rows = [label(f"{i}.jpg") for i in range(3)]
    items = [
        scored(rows[0], verdict=dict(rows[0].labels), latency_ms=1000.0),
        scored(rows[1], verdict=dict(rows[1].labels), latency_ms=3000.0),
        scored(rows[2], error="boom", latency_ms=50.0),
    ]

    summary = summarize_set("photo", "evidence-v1", items)

    assert summary["kind"] == "photo"
    assert summary["prompt_version"] == "evidence-v1"
    assert summary["n"] == 3
    assert summary["failed"] == 1
    assert summary["latency_ms"] == {"n": 2, "p50": 1000.0, "p95": 3000.0}
    assert [c["field"] for c in summary["confusion"]] == ["dam_state", "smoke"]


def test_parse_label_row_keeps_the_scored_fields():
    raw = {
        "file": "voice01.ogg",
        "object_path": "voice/voice01.ogg",
        "class": "voice_note",
        "subject": "canal_dam",
        "dam_state": "broken",
        "smoke": "none",
        "hot_ground_signs": "none",
        "open_flame": "no",
        "licence": "team",
    }

    row = parse_label_row(raw)

    assert row.file == "voice01.ogg"
    assert row.object_path == "voice/voice01.ogg"
    assert dict(row.labels) == {
        "subject": "canal_dam",
        "dam_state": "broken",
        "smoke": "none",
        "hot_ground_signs": "none",
        "open_flame": "no",
    }


def test_evidence_row_flattens_labels_and_verdict():
    row = label("a.jpg")
    item = scored(row, verdict={**row.labels, "smoke": "wisps"}, latency_ms=1234.5)

    flat = evidence_row(item, "2026-10-18T05:00:00+00:00", "gemini-x", "evidence-v1")

    assert flat["file"] == "a.jpg"
    assert flat["kind"] == "photo"
    assert flat["label_smoke"] == "none"
    assert flat["verdict_smoke"] == "wisps"
    assert flat["latency_ms"] == 1234.5
    assert flat["error"] is None
    assert flat["model"] == "gemini-x"


def test_evidence_row_of_a_failed_read_has_no_verdict():
    item = scored(label("a.jpg"), error="boom")

    flat = evidence_row(item, "2026-10-18T05:00:00+00:00", "gemini-x", "evidence-v1")

    assert flat["verdict_dam_state"] is None
    assert flat["error"] == "boom"
