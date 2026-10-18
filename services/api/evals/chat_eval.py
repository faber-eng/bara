import asyncio
import json
import math
import os
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from adapters.gemini import ModelGateway, build_vertex_clients
from casework.chat import (
    CHAT_PROMPT_VERSION,
    ChatOutput,
    ChatTurn,
    TaskContext,
    flag_blocked,
    generation_config,
    render_chat,
    task_facts,
)
from config import load_settings
from contracts import Language
from domain.case_view import format_local
from domain.chat_wording import leaks_internal_words
from tests.fakes import make_case, make_task, make_volunteer

REPO_ROOT = Path(__file__).resolve().parents[3]
OUTPUT_PATH = REPO_ROOT / "docs" / "eval" / "chat.json"
REPLY_TIMEOUT_SECONDS = 15.0
DEADLINE = datetime(2026, 10, 21, 3, 59, tzinfo=UTC)
ZONE = "Asia/Jakarta"

BLOCKED = "blocked"
QUESTION = "question"

MESSAGES: dict[Language, list[tuple[str, str]]] = {
    "en": [
        (BLOCKED, "I can't reach the dam, the road is flooded"),
        (BLOCKED, "The dam is gone, there is nothing left to check"),
        (BLOCKED, "No boat today, I cannot cross the canal"),
        (BLOCKED, "Road blocked by a fallen tree and water, I am turning back"),
        (QUESTION, "What do I need to send?"),
        (QUESTION, "When is my deadline?"),
        (QUESTION, "Where exactly do I go?"),
        (QUESTION, "I am at the dam now, what should I do first?"),
    ],
    "id": [
        (BLOCKED, "Saya tidak bisa sampai, jalan banjir"),
        (BLOCKED, "Sekat kanalnya hilang, tidak ada yang bisa dicek"),
        (BLOCKED, "Tidak ada perahu hari ini, saya tidak bisa menyeberang"),
        (BLOCKED, "Jalan tertutup pohon tumbang dan air, saya balik lagi"),
        (QUESTION, "Apa yang harus saya kirim?"),
        (QUESTION, "Kapan batas waktu saya?"),
        (QUESTION, "Saya harus ke mana tepatnya?"),
        (QUESTION, "Saya sudah di lokasi, apa yang harus saya lakukan dulu?"),
    ],
}


@dataclass(frozen=True)
class Sample:
    language: Language
    kind: str
    message: str
    reply: str
    needs_ops_model: bool
    needs_ops: bool
    names_task: bool
    names_deadline: bool
    code_word: bool
    seconds: float


def build_turn(language: Language) -> ChatTurn:
    volunteer = make_volunteer(language=language)
    case = make_case()
    task = make_task(deadline_at=DEADLINE)
    context = TaskContext(task, case, format_local(DEADLINE, ZONE))
    return ChatTurn(volunteer, language, context)


def contains(reply: str, fact: str) -> bool:
    return fact.casefold() in reply.casefold()


async def run_message(
    gateway: ModelGateway, language: Language, kind: str, message: str
) -> Sample:
    turn = build_turn(language)
    started = time.perf_counter()
    response = await gateway.generate(
        "fast",
        render_chat(turn, message),
        generation_config(REPLY_TIMEOUT_SECONDS),
    )
    seconds = time.perf_counter() - started
    output = ChatOutput.model_validate_json(response.text or "")
    flagged = flag_blocked(turn, message, output)
    facts = task_facts(turn.context, language) or {}
    return Sample(
        language=language,
        kind=kind,
        message=message,
        reply=output.text,
        needs_ops_model=output.needs_ops,
        needs_ops=flagged.needs_ops,
        names_task=contains(output.text, facts["task"]),
        names_deadline=contains(output.text, facts["deadline"]),
        code_word=leaks_internal_words(output.text)
        or leaks_internal_words(output.text_en),
        seconds=seconds,
    )


def percentile(values: list[float], share: float) -> float:
    ordered = sorted(values)
    rank = max(math.ceil(share * len(ordered)) - 1, 0)
    return ordered[rank]


def rate(samples: list[Sample], test) -> float:
    return sum(1 for sample in samples if test(sample)) / len(samples)


def summarize(samples: list[Sample]) -> dict:
    blocked = [sample for sample in samples if sample.kind == BLOCKED]
    seconds = [sample.seconds for sample in samples]
    return {
        "n": len(samples),
        "blocked_needs_ops_after_rule": rate(blocked, lambda s: s.needs_ops),
        "blocked_needs_ops_model_only": rate(blocked, lambda s: s.needs_ops_model),
        "names_task_and_deadline": rate(
            samples, lambda s: s.names_task and s.names_deadline
        ),
        "code_words": sum(1 for sample in samples if sample.code_word),
        "latency_p50_s": round(percentile(seconds, 0.5), 2),
        "latency_p95_s": round(percentile(seconds, 0.95), 2),
    }


async def run_all(gateway: ModelGateway) -> list[Sample]:
    samples = []
    for language, items in MESSAGES.items():
        for kind, message in items:
            samples.append(await run_message(gateway, language, kind, message))
    return samples


def main() -> None:
    os.environ.setdefault("GOOGLE_GENAI_USE_ENTERPRISE", "True")
    settings = load_settings()
    gateway = ModelGateway(settings.models, build_vertex_clients(settings))
    samples = asyncio.run(run_all(gateway))
    result = {
        "run_at": datetime.now(UTC).isoformat(),
        "prompt_version": CHAT_PROMPT_VERSION,
        "model": settings.models.for_role("fast").model,
        "summary": summarize(samples),
        "samples": [
            {**sample.__dict__, "seconds": round(sample.seconds, 2)}
            for sample in samples
        ],
    }
    OUTPUT_PATH.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
