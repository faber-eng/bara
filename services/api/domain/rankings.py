from contracts import RankedCell


def newest_week_by_rank(cells: list[RankedCell]) -> list[RankedCell]:
    if not cells:
        return []
    newest = max(cell.week_start for cell in cells)
    current = [cell for cell in cells if cell.week_start == newest]
    return sorted(current, key=lambda cell: cell.rank)
