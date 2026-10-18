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

WHAT_TO_SEND: dict[Language, dict[TaskType, str]] = {
    "id": {
        "dam_check": "foto sekat kanal dan tinggi air di kanal",
        "dam_repair": "foto sekat kanal yang sudah diperbaiki",
        "patrol_recheck": "foto tanah yang memperlihatkan asap atau panas, jika ada",
    },
    "en": {
        "dam_check": "a photo of the canal dam and the water level in the canal",
        "dam_repair": "a photo of the repaired canal dam",
        "patrol_recheck": "a photo of the ground, showing any smoke or heat",
    },
    "ms": {
        "dam_check": "foto tebatan kanal dan paras air di kanal",
        "dam_repair": "foto tebatan kanal yang telah dibaiki",
        "patrol_recheck": "foto tanah yang menunjukkan asap atau haba, jika ada",
    },
    "fr": {
        "dam_check": "une photo du barrage du canal et du niveau d'eau du canal",
        "dam_repair": "une photo du barrage du canal réparé",
        "patrol_recheck": "une photo du sol montrant toute fumée ou chaleur",
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
