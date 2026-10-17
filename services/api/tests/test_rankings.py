from datetime import date

from domain.rankings import newest_week_by_rank
from tests.fakes import make_ranked_cell

THIS_WEEK = date(2026, 10, 12)
LAST_WEEK = date(2026, 10, 5)


def test_newest_week_by_rank_drops_older_weeks_and_orders_by_rank():
    cells = [
        make_ranked_cell(cell_id="old", rank=1, week_start=LAST_WEEK),
        make_ranked_cell(cell_id="b", rank=3, week_start=THIS_WEEK),
        make_ranked_cell(cell_id="a", rank=2, week_start=THIS_WEEK),
    ]

    assert [cell.cell_id for cell in newest_week_by_rank(cells)] == ["a", "b"]


def test_newest_week_by_rank_of_nothing_is_empty():
    assert newest_week_by_rank([]) == []
