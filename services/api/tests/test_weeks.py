from datetime import date

import pytest

from domain.weeks import iso_week_label


@pytest.mark.parametrize(
    ("day", "label"),
    [
        (date(2026, 10, 12), "2026-W42"),
        (date(2026, 1, 1), "2026-W01"),
        (date(2027, 1, 1), "2026-W53"),
    ],
)
def test_iso_week_label(day, label):
    assert iso_week_label(day) == label
