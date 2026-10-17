import json
import random
from pathlib import Path

SEED = 20260720
CELL_COUNT = 200
DAM_COUNT = 50
OUTPUT = Path(__file__).resolve().parents[1] / "data" / "fixtures" / "rankings_riau_200.json"
DAM_STATES = ["intact", "damaged", "broken", "overtopped", "unknown"]
RANK_CHANGES = [None, 0, 1, 2, 3, -1, -2, -4]


def cell_scores(rng: random.Random) -> list[float]:
    scores = {round(rng.uniform(12.0, 97.0), 1) for _ in range(CELL_COUNT * 3)}
    return sorted(scores, reverse=True)[:CELL_COUNT]


def build_cell(rng: random.Random, rank: int, score: float) -> dict:
    stale = rng.random() < 0.15
    deficit = round(min(0.95, max(-0.2, score / 100 - 0.05 + rng.uniform(-0.1, 0.1))), 2)
    canal = round(rng.uniform(60.0, 2800.0), 1)
    explained = rng.random() < 0.3
    cell_id = f"riau-{rank + 100:04d}"
    s1 = None if stale else round(rng.uniform(-3.4, 0.6), 1)
    explanation = None
    if explained:
        explanation = {
            "text": f"Ranks {rank} because rain is {int(deficit * 100)}% below normal "
            f"and a canal runs {int(canal)} m away.",
            "cited": {"rain_deficit_pct": deficit, "canal_dist_m": canal},
        }
    return {
        "cell_id": cell_id,
        "region": "riau",
        "week_start": "2026-07-20",
        "centroid": {
            "lat": round(0.2 + rng.uniform(0.0, 0.6), 4),
            "lon": round(101.8 + rng.uniform(0.0, 0.7), 4),
        },
        "components": {
            "s1_anom_db": s1,
            "rain_30d_mm": round(rng.uniform(20.0, 160.0), 1),
            "rain_deficit_pct": deficit,
            "canal_dist_m": canal,
            "peat_class": rng.choice([1, 2]),
        },
        "drying_score": score,
        "rank": rank,
        "rank_change": rng.choice(RANK_CHANGES),
        "stale_s1": stale,
        "explanation": explanation,
    }


def build_dam(rng: random.Random, index: int, cell: dict) -> dict:
    state = rng.choice(DAM_STATES)
    checked = None if state == "unknown" else "2026-07-19T10:42:00+07:00"
    return {
        "dam_id": f"dam-riau-{index + 1:03d}",
        "region": "riau",
        "cell_id": cell["cell_id"],
        "point": {
            "lat": round(cell["centroid"]["lat"] + 0.001, 4),
            "lon": round(cell["centroid"]["lon"] + 0.001, 4),
        },
        "last_state": state,
        "last_checked_at": checked,
        "drying_score": cell["drying_score"],
        "rank": cell["rank"],
        "example": True,
    }


def build_rankings() -> dict:
    rng = random.Random(SEED)
    scores = cell_scores(rng)
    cells = [build_cell(rng, rank, score) for rank, score in enumerate(scores, start=1)]
    dam_cells = rng.sample(cells, DAM_COUNT)
    dams = [build_dam(rng, index, cell) for index, cell in enumerate(dam_cells)]
    dams.sort(key=lambda dam: dam["rank"])
    return {"region": "riau", "week": "2026-W30", "cells": cells, "dams": dams}


def main() -> None:
    OUTPUT.write_text(json.dumps(build_rankings(), indent=2) + "\n")


if __name__ == "__main__":
    main()
