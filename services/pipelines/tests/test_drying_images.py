from datetime import date

from ee_lib import drying
from ee_lib.config import load_data_config


class StubImage:
    def __init__(self, bands: int):
        self.bands = bands

    def median(self) -> "StubImage":
        return self


class StubPasses:
    def __init__(self, bands: int):
        self.bands = bands
        self.merged: list[object] = []

    def filter(self, _condition: object) -> "StubPasses":
        return self

    def filterDate(self, _start: str, _end: str) -> "StubPasses":
        return self

    def map(self, _function: object) -> "StubPasses":
        return self

    def merge(self, other: object) -> StubImage:
        self.merged.append(other)
        return StubImage(self.bands + 1)


def test_the_wet_baseline_of_an_empty_early_january_year_keeps_its_vv_band(
    config_dir, monkeypatch
):
    masked = object()
    monkeypatch.setattr(drying, "masked_band", lambda: masked)
    monkeypatch.setattr(drying.ee.Filter, "calendarRange", lambda *_: object())
    monkeypatch.setattr(drying.ee.Filter, "Or", lambda *_: object())
    passes = StubPasses(bands=0)
    data = load_data_config(config_dir)

    baseline = drying.wet_baseline(passes, data, 2026)

    assert passes.merged == [masked]
    assert baseline.bands == 1


def test_the_smoothed_median_merges_the_same_masked_band(monkeypatch):
    masked = object()
    monkeypatch.setattr(drying, "masked_band", lambda: masked)
    passes = StubPasses(bands=0)
    span = drying.DateRange(date(2025, 12, 31), date(2026, 1, 12))

    drying.smoothed_median(passes, span)

    assert passes.merged == [masked]
