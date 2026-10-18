import re

from contracts import Case, Language, TaskType

TASK_PHRASES: dict[Language, dict[TaskType, str]] = {
    "id": {
        "dam_check": "periksa sekat kanal",
        "dam_repair": "perbaiki sekat kanal",
        "patrol_recheck": "periksa ulang lahan bekas terbakar",
    },
    "en": {
        "dam_check": "check the canal dam",
        "dam_repair": "repair the canal dam",
        "patrol_recheck": "re-check the burned land",
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

AREA_FORMATS: dict[Language, str] = {
    "id": "di {region}",
    "en": "in {region}",
    "ms": "di {region}",
    "fr": "à {region}",
}

INTERNAL_WORDS = re.compile(r"\b[a-z]+(?:_[a-z0-9]+)+\b|\bdam-[a-z]+-\d+\b")


def task_phrase(task_type: TaskType, case: Case, language: Language) -> str:
    area = AREA_FORMATS[language].format(region=case.region.title())
    return f"{TASK_PHRASES[language][task_type]} {area}"


def leaks_internal_words(text: str) -> bool:
    return INTERNAL_WORDS.search(text) is not None
