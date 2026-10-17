import asyncio

from casework.evidence_eval import EvidenceEvaluator
from casework.evidence_reader import ReaderFailed
from casework.media import PreparedMedia, UnreadableMedia
from contracts import Verdict
from domain.evidence_eval import LabelRow


def verdict(**values):
    fields = {
        "subject": "canal_dam",
        "dam_state": "broken",
        "smoke": "none",
        "hot_ground_signs": "none",
        "open_flame": "no",
        "transcript": None,
        "transcript_en": None,
        "reasons": ["gap in the dam"],
        "confidence": 0.9,
        "needs_human": False,
    }
    fields.update(values)
    return Verdict.model_validate(fields)


def row(file, subject="canal_dam"):
    labels = {
        "subject": subject,
        "dam_state": "broken",
        "smoke": "none",
        "hot_ground_signs": "none",
        "open_flame": "no",
    }
    return LabelRow(file=file, object_path=f"photos/{file}", labels=labels)


class ScriptedReader:
    def __init__(self, replies):
        self.replies = replies
        self.calls = []
        self.active = 0
        self.most_active = 0

    async def read(self, media, task_type):
        self.calls.append((media.data, task_type))
        self.active += 1
        self.most_active = max(self.most_active, self.active)
        await asyncio.sleep(0)
        self.active -= 1
        reply = self.replies[media.data]
        if isinstance(reply, Exception):
            raise reply
        return reply


async def prepare(kind, data):
    if data == b"bad":
        raise UnreadableMedia("the file is not a readable image")
    return PreparedMedia(data, "image/jpeg", kind)


def ticking_timer():
    ticks = iter(float(n) for n in range(1000))
    return lambda: next(ticks)


def test_each_row_is_read_with_its_task_type_and_timed():
    reader = ScriptedReader(
        {b"dam": verdict(), b"peat": verdict(subject="burned_peat")}
    )
    evaluator = EvidenceEvaluator(
        reader, prepare=prepare, timer=ticking_timer(), concurrency=1
    )
    rows = [row("dam.jpg"), row("peat.jpg", subject="burned_peat")]
    data = {"dam.jpg": b"dam", "peat.jpg": b"peat"}

    items = asyncio.run(evaluator.score_all(rows, lambda r: data[r.file]))

    assert [item.row.file for item in items] == ["dam.jpg", "peat.jpg"]
    assert sorted(reader.calls) == [(b"dam", "dam_check"), (b"peat", "patrol_recheck")]
    assert items[0].verdict["dam_state"] == "broken"
    assert all(item.latency_ms == 1000.0 for item in items)
    assert all(item.error is None for item in items)


def test_a_failed_read_or_unreadable_file_is_kept_with_its_error():
    reader = ScriptedReader({b"dam": ReaderFailed("the model call failed: 500")})
    evaluator = EvidenceEvaluator(reader, prepare=prepare, timer=ticking_timer())
    rows = [row("dam.jpg"), row("bad.jpg")]
    data = {"dam.jpg": b"dam", "bad.jpg": b"bad"}

    items = asyncio.run(evaluator.score_all(rows, lambda r: data[r.file]))

    assert items[0].verdict is None
    assert items[0].error == "the model call failed: 500"
    assert items[1].error == "the file is not a readable image"


def test_reads_run_at_most_concurrency_at_a_time():
    replies = {f"p{n}.jpg".encode(): verdict() for n in range(6)}
    reader = ScriptedReader(replies)
    evaluator = EvidenceEvaluator(reader, prepare=prepare, concurrency=2)
    rows = [row(f"p{n}.jpg") for n in range(6)]

    asyncio.run(evaluator.score_all(rows, lambda r: r.file.encode()))

    assert reader.most_active <= 2
    assert len(reader.calls) == 6


def test_an_unexpected_error_fails_that_item_and_keeps_the_rest():
    reader = ScriptedReader({b"dam": TimeoutError("read timed out"), b"ok": verdict()})
    evaluator = EvidenceEvaluator(reader, prepare=prepare)
    rows = [row("dam.jpg"), row("ok.jpg")]
    data = {"dam.jpg": b"dam", "ok.jpg": b"ok"}

    items = asyncio.run(evaluator.score_all(rows, lambda r: data[r.file]))

    assert items[0].error == "TimeoutError: read timed out"
    assert items[1].error is None
