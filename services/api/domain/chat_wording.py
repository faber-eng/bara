import re
from typing import Literal

from contracts import Case, Language, TaskType

PlaceKind = Literal["dam", "area"]

TASK_NAMES: dict[Language, dict[TaskType, str]] = {
    "id": {
        "dam_check": "cek sekat kanal",
        "dam_repair": "perbaiki sekat kanal",
        "patrol_recheck": "cek ulang lahan bekas terbakar",
    },
    "en": {
        "dam_check": "check the canal dam",
        "dam_repair": "repair the canal dam",
        "patrol_recheck": "re-check the burned area",
    },
    "ms": {
        "dam_check": "periksa tebatan kanal",
        "dam_repair": "baiki tebatan kanal",
        "patrol_recheck": "periksa semula kawasan terbakar",
    },
    "fr": {
        "dam_check": "vérifier le barrage du canal",
        "dam_repair": "réparer le barrage du canal",
        "patrol_recheck": "revérifier la zone brûlée",
    },
}

PLACE_KINDS: dict[Language, dict[PlaceKind, str]] = {
    "id": {"dam": "sekat kanal", "area": "lahan bekas terbakar"},
    "en": {"dam": "the canal dam", "area": "the burned area"},
    "ms": {"dam": "tebatan kanal", "area": "kawasan terbakar"},
    "fr": {"dam": "le barrage du canal", "area": "la zone brûlée"},
}

PLACE_FORMATS: dict[Language, str] = {
    "id": "{kind} di {region}",
    "en": "{kind} in {region}",
    "ms": "{kind} di {region}",
    "fr": "{kind} à {region}",
}

INTERNAL_WORDS = re.compile(r"\b[a-z]+(?:_[a-z0-9]+)+\b|\bdam-[a-z]+-\d+\b")


def task_name(task_type: TaskType, language: Language) -> str:
    return TASK_NAMES[language][task_type]


def place_label(case: Case, language: Language) -> str:
    kind: PlaceKind = "area" if case.dam_id is None else "dam"
    return PLACE_FORMATS[language].format(
        kind=PLACE_KINDS[language][kind], region=case.region.title()
    )


def leaks_internal_words(text: str) -> bool:
    return INTERNAL_WORDS.search(text) is not None
