from dataclasses import dataclass

from contracts import AreaCell, GeoPoint

TOP_CELLS = 20
SCORE_DECIMALS = 1
COORD_DECIMALS = 5


@dataclass(frozen=True)
class ScoredAreaCell:
    cell_id: str
    lat: float
    lon: float
    drying_score: float


@dataclass(frozen=True)
class AreaMeasure:
    peat_cells: int
    cells: list[ScoredAreaCell]
    tile_url_template: str | None


def ordered(cells: list[ScoredAreaCell]) -> list[ScoredAreaCell]:
    return sorted(cells, key=lambda cell: (-cell.drying_score, cell.cell_id))


def to_area_cells(cells: list[ScoredAreaCell]) -> list[AreaCell]:
    return [
        AreaCell(
            cell_id=cell.cell_id,
            centroid=GeoPoint(
                lat=round(cell.lat, COORD_DECIMALS), lon=round(cell.lon, COORD_DECIMALS)
            ),
            drying_score=round(cell.drying_score, SCORE_DECIMALS),
            rank=rank,
        )
        for rank, cell in enumerate(ordered(cells)[:TOP_CELLS], 1)
    ]
