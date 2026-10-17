import re
from dataclasses import dataclass

from ee_lib.peat import PEAT_CLASSES

GRID_INDEX = re.compile(r"^(-?\d+),(-?\d+)$")


class MalformedCell(ValueError):
    pass


@dataclass(frozen=True)
class StagedCell:
    cell_id: str
    region: str
    geometry: dict
    peat_class: int


def cell_id(region: str, grid_index: object) -> str:
    match = GRID_INDEX.match(grid_index) if isinstance(grid_index, str) else None
    if match is None:
        raise MalformedCell(f"grid index {grid_index!r} is not 'x,y'")
    x, y = match.groups()
    return f"{region}-{x}-{y}"


def peat_class(mode: float | None) -> int | None:
    if mode is None:
        return None
    for value in PEAT_CLASSES:
        if mode == value:
            return value
    return None


def staged_cell(region: str, feature: dict) -> StagedCell | None:
    properties = feature.get("properties") or {}
    peat = peat_class(properties.get("peat_mode"))
    if peat is None:
        return None
    identifier = cell_id(region, properties.get("grid_index"))
    geometry = feature.get("geometry")
    if not isinstance(geometry, dict):
        raise MalformedCell(f"cell {identifier} has no geometry")
    return StagedCell(identifier, region, geometry, peat)


def staged_cells(region: str, features: list[dict]) -> list[StagedCell]:
    cells: list[StagedCell] = []
    seen: set[str] = set()
    for feature in features:
        cell = staged_cell(region, feature)
        if cell is None:
            continue
        if cell.cell_id in seen:
            raise MalformedCell(f"cell {cell.cell_id} appears twice")
        seen.add(cell.cell_id)
        cells.append(cell)
    return cells
