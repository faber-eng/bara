import pytest

from domain.chat_blocked import reports_blocked


@pytest.mark.parametrize(
    "text",
    [
        "I can't reach the dam, the road is flooded",
        "I can’t reach the dam",
        "Road flooded, turn back",
        "The dam is gone",
        "There is no boat today",
        "Saya tidak bisa sampai, jalan banjir",
        "Sekat jebol dan tidak ada perahu",
        "Saya tak dapat sampai ke tebatan",
        "Jalan banjir, tiada bot",
        "Je ne peux pas atteindre le barrage",
        "La route inondée bloque tout",
        "Il n'y a pas de bateau",
    ],
)
def test_a_clear_blocked_report_is_detected(text):
    assert reports_blocked(text)


@pytest.mark.parametrize(
    "text",
    [
        "What is my deadline?",
        "I am at the dam now",
        "Saya sudah di lokasi",
        "Apa yang harus saya foto?",
        "Je suis arrivé au barrage",
        "",
    ],
)
def test_a_question_or_progress_report_is_not_blocked(text):
    assert not reports_blocked(text)
