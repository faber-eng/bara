from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from contracts import CaseType, Smoke, TaskType
from domain.escalation import (
    DRYING_LIMIT,
    REIGNITE_LIMIT,
    REPEAT_ATTEMPT,
    FieldSigns,
    OverdueTask,
)


@dataclass(frozen=True)
class BriefFacts:
    case_type: CaseType
    cell_id: str
    dam_id: str | None
    drying_score: float | None
    p_reignite: float | None
    smoke_seen_before: bool
    field_signs: FieldSigns | None
    overdue_task: OverdueTask | None
    photo_count: int


@dataclass(frozen=True)
class Wording:
    decimal_mark: str
    keys: tuple[str, str, str]
    case_types: Mapping[CaseType, str]
    task_types: Mapping[TaskType, str]
    smoke: Mapping[Smoke, str]
    actions: Mapping[CaseType, str]
    cell: str
    dam: str
    found: str
    drying: str
    reignite: str
    above_limit: str
    at_limit: str
    smoke_seen: str
    overdue: str
    repeat: str
    signs: str
    open_flame: str
    hot_ground: str
    sign_joiner: str
    no_photo: str
    no_fire_in_photos: str
    needed_now: str


@dataclass(frozen=True)
class Phrases:
    found: str
    reasons: list[str]
    action: str


INDONESIAN = Wording(
    decimal_mark=",",
    keys=("temuan", "alasan", "tindakan"),
    case_types=MappingProxyType(
        {
            "dam_risk": "Risiko bendungan",
            "reignition": "Risiko api menyala kembali",
            "hotspot": "Titik panas",
        }
    ),
    task_types=MappingProxyType(
        {
            "dam_check": "pemeriksaan bendungan",
            "dam_repair": "perbaikan bendungan",
            "patrol_recheck": "patroli ulang",
        }
    ),
    smoke=MappingProxyType({"wisps": "asap tipis", "plume": "asap tebal"}),
    actions=MappingProxyType(
        {
            "dam_risk": "Kirim regu untuk memeriksa dan mengamankan bendungan.",
            "reignition": "Kirim regu untuk memeriksa lokasi dan memadamkan api.",
            "hotspot": "Kirim regu untuk memeriksa lokasi dan memadamkan api.",
        }
    ),
    cell="sel {cell_id}",
    dam=", bendungan {dam_id}",
    found="{case_type} di {place}",
    drying="skor kekeringan {value}",
    reignite="peluang api menyala kembali {value}",
    above_limit=", di atas batas {limit}",
    at_limit=", tepat di batas {limit}",
    smoke_seen="asap pernah terlihat di sel ini",
    overdue="tugas {task_type} lewat tenggat",
    repeat=" setelah {attempt} orang diminta",
    signs="foto dari lapangan menunjukkan {signs}",
    open_flame="api terbuka",
    hot_ground="tanda tanah panas",
    sign_joiner=" dan ",
    no_photo="belum ada foto dari lapangan",
    no_fire_in_photos="foto dari lapangan tidak menunjukkan tanda api",
    needed_now="Regu dibutuhkan sekarang karena {reasons}.",
)

ENGLISH = Wording(
    decimal_mark=".",
    keys=("found", "reasons", "action"),
    case_types=MappingProxyType(
        {
            "dam_risk": "Dam risk",
            "reignition": "Re-ignition risk",
            "hotspot": "Hotspot",
        }
    ),
    task_types=MappingProxyType(
        {
            "dam_check": "dam check",
            "dam_repair": "dam repair",
            "patrol_recheck": "patrol recheck",
        }
    ),
    smoke=MappingProxyType({"wisps": "thin smoke", "plume": "a thick smoke plume"}),
    actions=MappingProxyType(
        {
            "dam_risk": "Send a crew to check and secure the dam.",
            "reignition": "Send a crew to check the site and put out the fire.",
            "hotspot": "Send a crew to check the site and put out the fire.",
        }
    ),
    cell="cell {cell_id}",
    dam=", dam {dam_id}",
    found="{case_type} in {place}",
    drying="drying score {value}",
    reignite="re-ignition chance {value}",
    above_limit=", above the limit of {limit}",
    at_limit=", at the limit of {limit}",
    smoke_seen="smoke was seen in this cell before",
    overdue="the {task_type} task is past its deadline",
    repeat=" after {attempt} people were asked",
    signs="a field photo shows {signs}",
    open_flame="open flame",
    hot_ground="signs of hot ground",
    sign_joiner=" and ",
    no_photo="no field photo yet",
    no_fire_in_photos="the field photos show no fire signs",
    needed_now="A crew is needed now because {reasons}.",
)


def decimal_text(value: float, wording: Wording) -> str:
    rounded = round(value, 1)
    if rounded.is_integer():
        return str(int(rounded))
    return f"{rounded:.1f}".replace(".", wording.decimal_mark)


def percent_text(value: float) -> str:
    return f"{round(value * 100)}%"


def limit_suffix(value: float, limit: float, limit_text: str, wording: Wording) -> str:
    if value < limit:
        return ""
    if value == limit:
        return wording.at_limit.format(limit=limit_text)
    return wording.above_limit.format(limit=limit_text)


def place_text(facts: BriefFacts, wording: Wording) -> str:
    cell = wording.cell.format(cell_id=facts.cell_id)
    if facts.dam_id is None:
        return cell
    return cell + wording.dam.format(dam_id=facts.dam_id)


def found_text(facts: BriefFacts, wording: Wording) -> str:
    return wording.found.format(
        case_type=wording.case_types[facts.case_type],
        place=place_text(facts, wording),
    )


def drying_reason(score: float, wording: Wording) -> str:
    limit_text = decimal_text(DRYING_LIMIT, wording)
    value = wording.drying.format(value=decimal_text(score, wording))
    return value + limit_suffix(score, DRYING_LIMIT, limit_text, wording)


def reignite_reason(chance: float, wording: Wording) -> str:
    value = wording.reignite.format(value=percent_text(chance))
    return value + limit_suffix(
        chance, REIGNITE_LIMIT, percent_text(REIGNITE_LIMIT), wording
    )


def overdue_reason(task: OverdueTask, wording: Wording) -> str:
    text = wording.overdue.format(task_type=wording.task_types[task.task_type])
    if task.attempt < REPEAT_ATTEMPT:
        return text
    return text + wording.repeat.format(attempt=task.attempt)


def sign_names(signs: FieldSigns, wording: Wording) -> list[str]:
    names: list[str] = []
    smoke = wording.smoke.get(signs.smoke)
    if smoke is not None:
        names.append(smoke)
    if signs.open_flame:
        names.append(wording.open_flame)
    if signs.hot_ground:
        names.append(wording.hot_ground)
    return names


def evidence_reason(facts: BriefFacts, wording: Wording) -> str:
    if facts.field_signs is not None:
        names = sign_names(facts.field_signs, wording)
        return wording.signs.format(signs=wording.sign_joiner.join(names))
    if facts.photo_count == 0:
        return wording.no_photo
    return wording.no_fire_in_photos


def reasons(facts: BriefFacts, wording: Wording) -> list[str]:
    found: list[str] = []
    if facts.drying_score is not None:
        found.append(drying_reason(facts.drying_score, wording))
    if facts.p_reignite is not None:
        found.append(reignite_reason(facts.p_reignite, wording))
    if facts.smoke_seen_before:
        found.append(wording.smoke_seen)
    if facts.overdue_task is not None:
        found.append(overdue_reason(facts.overdue_task, wording))
    found.append(evidence_reason(facts, wording))
    return found


def phrases(facts: BriefFacts, wording: Wording) -> Phrases:
    return Phrases(
        found=found_text(facts, wording),
        reasons=reasons(facts, wording),
        action=wording.actions[facts.case_type],
    )


def phrase_block(facts: BriefFacts, wording: Wording) -> dict[str, object]:
    found_key, reasons_key, action_key = wording.keys
    parts = phrases(facts, wording)
    return {
        found_key: parts.found,
        reasons_key: parts.reasons,
        action_key: parts.action,
    }


def template_text(facts: BriefFacts, wording: Wording) -> str:
    parts = phrases(facts, wording)
    needed = wording.needed_now.format(reasons="; ".join(parts.reasons))
    return f"{parts.found}. {needed} {parts.action}"
