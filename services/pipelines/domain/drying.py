import math
import statistics
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date

from ee_lib.canals import CANAL_DECAY_M
from ee_lib.config import DryingWeights
from ee_lib.peat import PEAT_WEIGHTS

NEUTRAL_SCORE = 50.0


class MissingMeasurement(ValueError):
    pass


@dataclass(frozen=True)
class CellInput:
    cell_id: str
    peat_class: int
    canal_dist_m: float
    s1_recent_anom_db: float | None
    s1_previous_anom_db: float | None
    rain_30d_mm: float
    clim_rain_30d_mm: float


@dataclass(frozen=True)
class DryingRow:
    cell_id: str
    region: str
    week_start: date
    s1_anom_db: float | None
    stale_s1: bool
    rain_30d_mm: float
    rain_deficit_pct: float
    canal_dist_m: float
    peat_class: int
    drying_score: float
    rank: int


def rain_deficit_pct(rain_mm: float, clim_mm: float) -> float:
    if clim_mm == 0:
        if rain_mm > 0:
            return -1.0
        return 0.0
    return max(-1.0, min(1.0, 1 - rain_mm / clim_mm))


def canal_proximity(canal_dist_m: float) -> float:
    return math.exp(-canal_dist_m / CANAL_DECAY_M)


def peat_weight(peat_class: int) -> float:
    if peat_class not in PEAT_WEIGHTS:
        raise ValueError(f"peat class {peat_class!r} is not 1 or 2")
    return PEAT_WEIGHTS[peat_class]


def pick_s1(recent: float | None, previous: float | None) -> tuple[float | None, bool]:
    if recent is not None:
        return recent, False
    return previous, True


def zscores(values: Sequence[float | None]) -> list[float]:
    present = [value for value in values if value is not None]
    if not present:
        return [0.0 for _ in values]
    mean = statistics.fmean(present)
    spread = statistics.pstdev(present, mean)
    if spread == 0:
        return [0.0 for _ in values]
    return [0.0 if value is None else (value - mean) / spread for value in values]


def sigmoid_score(total: float) -> float:
    return 100 / (1 + math.exp(-total))


def rank_order(scores: Sequence[tuple[str, float]]) -> dict[str, int]:
    ordered = sorted(scores, key=lambda pair: (-pair[1], pair[0]))
    return {cell_id: position for position, (cell_id, _) in enumerate(ordered, 1)}


def weighted_totals(
    s1: Sequence[float | None],
    deficits: Sequence[float],
    cells: Sequence[CellInput],
    weights: DryingWeights,
) -> list[float]:
    s1_z = zscores(s1)
    deficit_z = zscores(deficits)
    canal_z = zscores([canal_proximity(cell.canal_dist_m) for cell in cells])
    peat_z = zscores([peat_weight(cell.peat_class) for cell in cells])
    return [
        weights.s1_anomaly * -s1_z[i]
        + weights.rain_deficit * deficit_z[i]
        + weights.canal_proximity * canal_z[i]
        + weights.peat_class * peat_z[i]
        for i in range(len(cells))
    ]


def score_cells(
    region: str, week_start: date, cells: Sequence[CellInput], weights: DryingWeights
) -> list[DryingRow]:
    picked = [pick_s1(c.s1_recent_anom_db, c.s1_previous_anom_db) for c in cells]
    s1 = [value for value, _ in picked]
    deficits = [rain_deficit_pct(c.rain_30d_mm, c.clim_rain_30d_mm) for c in cells]
    scores = [sigmoid_score(t) for t in weighted_totals(s1, deficits, cells, weights)]
    ranks = rank_order(
        [(c.cell_id, score) for c, score in zip(cells, scores, strict=True)]
    )
    rows = [
        DryingRow(
            cell_id=c.cell_id,
            region=region,
            week_start=week_start,
            s1_anom_db=s1_value,
            stale_s1=stale,
            rain_30d_mm=c.rain_30d_mm,
            rain_deficit_pct=deficit,
            canal_dist_m=c.canal_dist_m,
            peat_class=c.peat_class,
            drying_score=score,
            rank=ranks[c.cell_id],
        )
        for c, (s1_value, stale), deficit, score in zip(
            cells, picked, deficits, scores, strict=True
        )
    ]
    return sorted(rows, key=lambda row: row.rank)


def required_number(measured: Mapping[str, object], field: str, cell_id: str) -> float:
    value = measured.get(field)
    if not isinstance(value, int | float) or isinstance(value, bool):
        raise MissingMeasurement(f"cell {cell_id} has no {field}")
    return float(value)


def optional_number(measured: Mapping[str, object], field: str) -> float | None:
    value = measured.get(field)
    if isinstance(value, int | float) and not isinstance(value, bool):
        return float(value)
    return None


def join_measurements(
    cells: Sequence[Mapping[str, object]], measured: Sequence[Mapping[str, object]]
) -> list[CellInput]:
    by_id = {str(row.get("cell_id")): row for row in measured}
    joined: list[CellInput] = []
    for cell in cells:
        cell_id = str(cell["cell_id"])
        if cell_id not in by_id:
            raise MissingMeasurement(f"cell {cell_id} has no Earth Engine measurement")
        values = by_id[cell_id]
        joined.append(
            CellInput(
                cell_id=cell_id,
                peat_class=int(cell["peat_class"]),
                canal_dist_m=float(cell["canal_dist_m"]),
                s1_recent_anom_db=optional_number(values, "s1_recent_anom_db"),
                s1_previous_anom_db=optional_number(values, "s1_previous_anom_db"),
                rain_30d_mm=required_number(values, "rain_30d_mm", cell_id),
                clim_rain_30d_mm=required_number(values, "clim_rain_30d_mm", cell_id),
            )
        )
    return joined
