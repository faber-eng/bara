import pytest

from contracts import CitedValue
from domain.bulletin import (
    BulletinRejected,
    check_bulletin,
    summary_facts,
    template_bulletin,
)
from tests.fakes import make_public_summary

SUMMARY = make_public_summary()
TEXT_EN = "This week 12 cells are at high risk. 3 dams are broken."
TEXT_ID = "Minggu ini 12 sel berisiko tinggi. 3 bendungan rusak."
CITED = [
    CitedValue(field="high_risk_cells", value=12),
    CitedValue(field="dams_broken", value=3),
]


def check(text_id=TEXT_ID, text_en=TEXT_EN, cited=None):
    check_bulletin(text_id, text_en, CITED if cited is None else cited, SUMMARY)


def test_texts_whose_numbers_are_all_cited_and_exact_pass():
    check()


def test_a_cited_value_that_differs_from_the_summary_is_rejected():
    wrong = [CitedValue(field="high_risk_cells", value=13), CITED[1]]
    with pytest.raises(BulletinRejected, match="high_risk_cells"):
        check(cited=wrong)


def test_a_cited_field_outside_the_summary_is_rejected():
    with pytest.raises(BulletinRejected, match="humidity"):
        check(cited=[*CITED, CitedValue(field="humidity", value=4)])


def test_a_number_in_the_english_text_that_is_not_cited_is_rejected():
    with pytest.raises(BulletinRejected, match="45"):
        check(text_en=TEXT_EN + " 45 tasks were done.")


def test_a_number_in_the_indonesian_text_that_is_not_cited_is_rejected():
    with pytest.raises(BulletinRejected, match="45"):
        check(text_id=TEXT_ID + " 45 tugas selesai.")


def test_a_cited_value_missing_from_a_text_is_rejected():
    with pytest.raises(BulletinRejected, match="dams_broken"):
        check(text_id="Minggu ini 12 sel berisiko tinggi.")


def test_a_decimal_comma_in_the_indonesian_text_matches_the_cited_decimal():
    summary = make_public_summary(median_days_to_repair=2.5)
    cited = [CitedValue(field="median_days_to_repair", value=2.5)]
    check_bulletin(
        "Perbaikan butuh 2,5 hari.", "Repairs take 2.5 days.", cited, summary
    )


def test_a_zero_field_is_cited_and_written_as_zero():
    summary = make_public_summary(cases_open=0)
    cited = [CitedValue(field="cases_open", value=0)]
    check_bulletin("Tidak ada 0 kasus", "No cases: 0 open.", cited, summary)


def test_a_cited_field_that_is_null_in_the_summary_is_rejected():
    summary = make_public_summary(median_days_to_repair=None)
    cited = [CitedValue(field="median_days_to_repair", value=2.0)]
    with pytest.raises(BulletinRejected, match="median_days_to_repair"):
        check_bulletin("2 hari", "2 days", cited, summary)


def test_summary_facts_leave_out_null_fields_and_the_dates():
    summary = make_public_summary(median_days_to_repair=None)
    fields = [fact["field"] for fact in summary_facts(summary)]
    assert "median_days_to_repair" not in fields
    assert "data_as_of" not in fields
    assert "high_risk_cells" in fields


def test_the_template_passes_its_own_check_for_any_summary():
    for summary in (
        make_public_summary(),
        make_public_summary(cases_open=0, dams_broken=0, tasks_on_time_pct=None),
        make_public_summary(median_days_to_repair=None, tasks_on_time_pct=87.5),
    ):
        text_id, text_en, cited = template_bulletin(summary)
        check_bulletin(text_id, text_en, cited, summary)
