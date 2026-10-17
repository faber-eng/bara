from datetime import UTC, date, datetime

import pytest

from domain.reignition_scores import (
    FeatureAttribution,
    InvalidScore,
    event_score,
    fire_quiet_event,
    fires_to_publish,
    group_fires,
)

QUIET = date(2026, 8, 10)


def row(cell_id="riau-1-1", p=0.6, quiet=QUIET, **overrides):
    base = {
        "event_id": f"{cell_id}-20260801",
        "cell_id": cell_id,
        "region": "riau",
        "quiet_date": quiet,
        "p_reignite": p,
        "top_feature_attributions": [
            {"feature": "month", "attribution": 0.1},
            {"feature": "mean_confidence", "attribution": -0.3},
            {"feature": "prior_years_burned", "attribution": 0.2},
        ],
    }
    return {**base, **overrides}


def test_a_score_keeps_the_strongest_attributions_by_size():
    score = event_score(row())

    assert score.p_reignite == 0.6
    assert score.top_features == (
        FeatureAttribution("mean_confidence", -0.3),
        FeatureAttribution("prior_years_burned", 0.2),
        FeatureAttribution("month", 0.1),
    )


@pytest.mark.parametrize(
    "bad",
    [
        {"p_reignite": None},
        {"p_reignite": 1.2},
        {"p_reignite": True},
        {"quiet_date": "2026-08-10"},
        {"top_feature_attributions": [{"feature": "month"}]},
    ],
)
def test_a_malformed_prediction_is_refused(bad):
    with pytest.raises(InvalidScore):
        event_score(row(**bad))


def test_a_fire_is_the_cells_quiet_on_one_day_with_its_top_cells_first():
    scores = [
        event_score(row("riau-1-1", 0.4)),
        event_score(row("riau-1-2", 0.9)),
        event_score(row("riau-1-3", 0.7)),
        event_score(row("riau-1-4", 0.7)),
        event_score(row("riau-9-9", 0.8, quiet=date(2026, 8, 11))),
    ]

    fires = group_fires(scores, spots=3)

    assert [fire.event_id for fire in fires] == [
        "fire-riau-20260810",
        "fire-riau-20260811",
    ]
    assert [cell.cell_id for cell in fires[0].cells] == [
        "riau-1-2",
        "riau-1-3",
        "riau-1-4",
    ]


def test_publishing_takes_the_recent_fires_or_the_one_asked_for():
    scores = [
        event_score(row("riau-1-1", quiet=date(2026, 8, 1))),
        event_score(row("riau-1-2", quiet=date(2026, 8, 9))),
        event_score(row("riau-1-3", quiet=date(2026, 8, 10))),
    ]
    fires = group_fires(scores, spots=3)

    recent = fires_to_publish(fires, since=date(2026, 8, 9), only=None)
    asked = fires_to_publish(fires, since=date(2026, 8, 9), only=date(2026, 8, 1))

    assert [fire.quiet_date for fire in recent] == [date(2026, 8, 9), QUIET]
    assert [fire.quiet_date for fire in asked] == [date(2026, 8, 1)]


def test_the_event_carries_each_cell_with_its_p_reignite_and_top_features():
    fire = group_fires([event_score(row("riau-1-2", 0.9))], spots=3)[0]
    now = datetime(2026, 10, 18, 2, 0, tzinfo=UTC)

    event = fire_quiet_event(fire, "env-1", now, example=True)

    assert event.type == "fire.quiet"
    assert event.example is True
    assert event.region == "riau"
    assert event.payload.event_id == "fire-riau-20260810"
    cell = event.payload.cells[0]
    assert cell.cell_id == "riau-1-2"
    assert cell.p_reignite == 0.9
    assert [item.feature for item in cell.top_features] == [
        "mean_confidence",
        "prior_years_burned",
        "month",
    ]
