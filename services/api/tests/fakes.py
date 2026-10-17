import operator
from collections.abc import Callable, Mapping, Sequence
from types import SimpleNamespace

from google.api_core import exceptions as gax
from google.cloud.firestore_v1 import Increment
from google.genai import errors, types

from adapters.store import DocumentNotFound, Filter, Guard, GuardFailed, Put
from auth import InvalidToken
from contracts import ClockSettings, Contract


def api_error(code: int) -> errors.APIError:
    return errors.APIError(code, {"error": {"code": code, "message": f"status {code}"}})


class FakeModels:
    def __init__(self, outcomes: list[types.GenerateContentResponse | Exception]):
        self._outcomes = list(outcomes)
        self.calls: list[str] = []
        self.requests: list[tuple[object, object]] = []

    async def generate_content(
        self,
        *,
        model: str,
        contents: types.ContentListUnion,
        config: types.GenerateContentConfigOrDict | None = None,
    ) -> types.GenerateContentResponse:
        self.calls.append(model)
        self.requests.append((contents, config))
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class InMemoryClockStore:
    def __init__(self, settings: ClockSettings | None):
        self._settings = settings

    def get(self) -> ClockSettings | None:
        return self._settings

    def put(self, settings: ClockSettings) -> None:
        self._settings = settings

    def add_seconds(self, seconds: int, updated_by: str) -> None:
        current = self._settings.offset_seconds if self._settings else 0
        self._settings = ClockSettings(
            offset_seconds=current + seconds, updated_by=updated_by
        )


class FakeVerifier:
    def __init__(self, claims_by_token: dict[str, dict[str, object]]):
        self._claims_by_token = claims_by_token
        self.seen: list[str] = []

    def verify(self, token: str) -> dict[str, object]:
        self.seen.append(token)
        if token not in self._claims_by_token:
            raise InvalidToken("token rejected")
        return self._claims_by_token[token]


OPERATORS: dict[str, Callable[[object, object], bool]] = {
    "==": operator.eq,
    "<": operator.lt,
    "<=": operator.le,
    ">": operator.gt,
    ">=": operator.ge,
    "in": lambda actual, wanted: actual in wanted,
}


def matches(document: Mapping[str, object], filters: tuple[Filter, ...]) -> bool:
    return all(OPERATORS[f.op](document[f.field], f.value) for f in filters)


class InMemoryCollection[T: Contract]:
    def __init__(self, model: type[T]):
        self._model = model
        self._documents: dict[str, T] = {}

    def get(self, doc_id: str) -> T | None:
        return self._documents.get(doc_id)

    def put(self, doc_id: str, item: T) -> None:
        self._documents[doc_id] = item

    def create_if_absent(self, doc_id: str, item: T) -> bool:
        if doc_id in self._documents:
            return False
        self._documents[doc_id] = item
        return True

    def update(self, doc_id: str, fields: Mapping[str, object]) -> None:
        if doc_id not in self._documents:
            raise DocumentNotFound(doc_id)
        merged = {**self._documents[doc_id].model_dump(), **fields}
        self._documents[doc_id] = self._model.model_validate(merged)

    def add(self, doc_id: str, field: str, amount: int, fields: Mapping[str, object]):
        current = self._documents.get(doc_id)
        base = current.model_dump() if current else {field: 0}
        merged = {**base, **fields, field: base[field] + amount}
        self._documents[doc_id] = self._model.model_validate(merged)

    def where(self, *filters: Filter) -> list[T]:
        return [
            item for item in self._documents.values() if matches(dict(item), filters)
        ]

    def delete_many(self, doc_ids) -> None:
        for doc_id in list(doc_ids):
            self._documents.pop(doc_id, None)

    def put_many(self, items) -> None:
        self._documents.update(items)


class InMemoryTransactor:
    def __init__(self, collections: Mapping[str, InMemoryCollection], error=None):
        self._collections = collections
        self.error = error
        self.commits = 0

    def commit(self, guards: Sequence[Guard], writes) -> None:
        if self.error is not None:
            raise self.error
        for guard in guards:
            self._check(guard)
        for write in writes:
            self._apply(write)
        self.commits += 1

    def _check(self, guard: Guard) -> None:
        item = self._collections[guard.collection].get(guard.doc_id)
        if item is None or getattr(item, guard.field) != guard.expected:
            raise GuardFailed(f"{guard.collection}/{guard.doc_id}")

    def _apply(self, write) -> None:
        collection = self._collections[write.collection]
        if isinstance(write, Put):
            collection.put(write.doc_id, write.item)
            return
        collection.update(write.doc_id, write.fields)


class StubSnapshot:
    def __init__(self, data: dict[str, object] | None):
        self._data = data
        self.exists = data is not None

    def to_dict(self) -> dict[str, object] | None:
        return self._data


class StubDocumentRef:
    def __init__(self, store: dict[str, dict[str, object]], doc_id: str):
        self._store = store
        self._doc_id = doc_id

    def get(self) -> StubSnapshot:
        return StubSnapshot(self._store.get(self._doc_id))

    def set(self, data: dict[str, object], merge: bool = False) -> None:
        if not merge:
            self._store[self._doc_id] = dict(data)
            return
        document = self._store.setdefault(self._doc_id, {})
        for field, value in data.items():
            document[field] = self._merge_value(document.get(field), value)

    @staticmethod
    def _merge_value(current, value):
        if isinstance(value, Increment):
            return (current or 0) + value.value
        return value

    def remove(self) -> None:
        self._store.pop(self._doc_id, None)

    def create(self, data: dict[str, object]) -> None:
        if self._doc_id in self._store:
            raise gax.AlreadyExists("document exists")
        self._store[self._doc_id] = dict(data)

    def update(self, fields: Mapping[str, object]) -> None:
        if self._doc_id not in self._store:
            raise gax.NotFound("document missing")
        self._store[self._doc_id].update(fields)


class StubBatch:
    def __init__(self):
        self.operations: list[tuple[str, StubDocumentRef, dict | None]] = []
        self.commits = 0

    def delete(self, ref: StubDocumentRef) -> None:
        self.operations.append(("delete", ref, None))

    def set(self, ref: StubDocumentRef, data: dict) -> None:
        self.operations.append(("set", ref, data))

    def commit(self) -> None:
        for kind, ref, data in self.operations:
            if kind == "delete":
                ref.remove()
            else:
                ref.set(data)
        self.operations = []
        self.commits += 1


class StubQuery:
    def __init__(
        self, store: dict[str, dict[str, object]], filters: tuple[Filter, ...]
    ):
        self._store = store
        self._filters = filters

    def where(self, *, filter) -> "StubQuery":
        added = Filter(filter.field_path, filter.op_string, filter.value)
        return StubQuery(self._store, (*self._filters, added))

    def stream(self):
        return [
            StubSnapshot(data)
            for data in self._store.values()
            if matches(data, self._filters)
        ]


class StubCollectionRef(StubQuery):
    def document(self, doc_id: str) -> StubDocumentRef:
        return StubDocumentRef(self._store, doc_id)


class StubFirestoreClient:
    def __init__(self):
        self.stores: dict[str, dict[str, dict[str, object]]] = {}
        self.batches: list[StubBatch] = []

    def batch(self) -> StubBatch:
        self.batches.append(StubBatch())
        return self.batches[-1]

    def collection(self, name: str) -> StubCollectionRef:
        store = self.stores.setdefault(name, {})
        return StubCollectionRef(store, ())


class RecordingBlob:
    def __init__(self, name: str, calls: list[dict[str, object]]):
        self.name = name
        self._calls = calls

    def generate_signed_url(self, **kwargs) -> str:
        self._calls.append({"name": self.name, **kwargs})
        return f"https://storage.test/{self.name}?X-Goog-Signature=abc"


class RecordingBucket:
    def __init__(self):
        self.calls: list[dict[str, object]] = []

    def blob(self, name: str) -> RecordingBlob:
        return RecordingBlob(name, self.calls)


def fixed_signing_auth() -> SimpleNamespace:
    return SimpleNamespace(
        service_account_email="bara-api@example.iam.gserviceaccount.com",
        access_token="ya29.fake-token",
    )


def make_task(**overrides):
    from datetime import UTC, datetime

    from contracts import GeoPoint, Task

    fields = {
        "id": "t1",
        "case_id": "c1",
        "type": "dam_check",
        "assignee_id": "v1",
        "target": GeoPoint(lat=0.5, lon=101.4),
        "deadline_at": datetime(2026, 10, 20, 12, 0, tzinfo=UTC),
        "status": "open",
        "cloud_task_name": None,
        "attempt": 1,
        "created_at": datetime(2026, 10, 17, 12, 0, tzinfo=UTC),
        "done_at": None,
    }
    return Task(**{**fields, **overrides})


def make_case(**overrides):
    from datetime import UTC, datetime

    from contracts import Case, CaseRisk, HistoryFlags

    fields = {
        "id": "c1",
        "type": "dam_risk",
        "region": "riau",
        "cell_id": "cell-1",
        "dam_id": "dam-1",
        "event_id": None,
        "status": "open",
        "risk": CaseRisk(drying_score=80.0, p_reignite=None),
        "opened_at": datetime(2026, 10, 17, 12, 0, tzinfo=UTC),
        "closed_by": None,
        "closed_at": None,
        "history_flags": HistoryFlags(smoke_seen=False),
        "example": False,
    }
    return Case(**{**fields, **overrides})


class FakeSecretReader:
    def __init__(self, code: str | Exception = "bara-secret"):
        self._code = code
        self.reads = 0

    def join_code(self) -> str:
        self.reads += 1
        if isinstance(self._code, Exception):
            raise self._code
        return self._code


class FakeClaimsAdmin:
    def __init__(
        self,
        claims_by_uid: dict[str, dict[str, object]] | None = None,
        uid_by_email: dict[str, str] | None = None,
    ):
        self.claims_by_uid = claims_by_uid or {}
        self.uid_by_email = uid_by_email or {}
        self.writes: list[tuple[str, dict[str, object]]] = []
        self.fail_with: Exception | None = None

    def get_claims(self, uid: str) -> dict[str, object]:
        self._raise_if_failing()
        return dict(self.claims_by_uid.get(uid, {}))

    def set_claims(self, uid: str, claims: dict[str, object]) -> None:
        self._raise_if_failing()
        self.claims_by_uid[uid] = dict(claims)
        self.writes.append((uid, dict(claims)))

    def uid_for_email(self, email: str) -> str | None:
        self._raise_if_failing()
        return self.uid_by_email.get(email)

    def _raise_if_failing(self) -> None:
        if self.fail_with is not None:
            raise self.fail_with


def make_volunteer(**overrides):
    from contracts import Channels, GeoPoint, Volunteer

    fields = {
        "id": "v1",
        "name": "Sari",
        "role": "volunteer",
        "region": "riau",
        "home": GeoPoint(lat=0.5, lon=101.4),
        "language": "id",
        "channels": Channels(web=True, whatsapp=None),
        "available": True,
        "example": False,
    }
    return Volunteer(**{**fields, **overrides})


def make_contact(**overrides):
    from contracts import Channels, Contact

    fields = {
        "id": "ct1",
        "name": "Daops",
        "org": "Manggala Agni",
        "channels": Channels(web=True, whatsapp=None),
        "region": "riau",
        "example": True,
    }
    return Contact(**{**fields, **overrides})


def make_dam(**overrides):
    from contracts import Dam, GeoPoint

    fields = {
        "id": "dam-1",
        "point": GeoPoint(lat=0.5, lon=101.4),
        "canal_osm_id": None,
        "region": "riau",
        "last_state": "intact",
        "last_checked_at": None,
        "example": True,
    }
    return Dam(**{**fields, **overrides})


def make_evidence(**overrides):
    from contracts import Evidence

    fields = {
        "id": "e1",
        "task_id": "t1",
        "case_id": "c1",
        "kind": "photo",
        "gcs_uri": "gs://bucket/e1.jpg",
        "sha256": "0" * 64,
        "point": None,
        "captured_at": None,
        "verdict": None,
        "location_ok": None,
        "uploaded_by": "v1",
        "sample": False,
    }
    return Evidence(**{**fields, **overrides})


def make_message(**overrides):
    from datetime import UTC, datetime

    from contracts import Message

    fields = {
        "id": "m1",
        "thread": "volunteer",
        "to_id": "v1",
        "case_id": "c1",
        "lang": "id",
        "text": "halo",
        "text_en": "hello",
        "channel": "web",
        "created_at": datetime(2026, 10, 17, 12, 0, tzinfo=UTC),
        "delivered": True,
    }
    return Message(**{**fields, **overrides})


def make_escalation(**overrides):
    from datetime import UTC, datetime

    from contracts import Escalation, EscalationPack

    fields = {
        "id": "x1",
        "case_id": "c1",
        "contact_id": "ct1",
        "brief_id": "brief",
        "brief_en": "brief",
        "pack": EscalationPack(photos=[], map_url="https://maps.test/x", timeline=[]),
        "created_at": datetime(2026, 10, 17, 12, 0, tzinfo=UTC),
        "acknowledged_at": None,
    }
    return Escalation(**{**fields, **overrides})


def make_ranked_cell(**overrides):
    from datetime import date

    from contracts import GeoPoint, RankedCell, RankingComponents

    fields = {
        "cell_id": "riau-1-1",
        "region": "riau",
        "week_start": date(2026, 10, 12),
        "centroid": GeoPoint(lat=0.5, lon=101.4),
        "components": RankingComponents(
            s1_anom_db=-4.2,
            rain_30d_mm=180.0,
            rain_deficit_pct=0.31,
            canal_dist_m=140.0,
            peat_class=1,
        ),
        "drying_score": 90.0,
        "rank": 1,
        "rank_change": None,
        "stale_s1": False,
        "explanation": None,
    }
    return RankedCell(**{**fields, **overrides})


def make_agent_run(**overrides):
    from datetime import UTC, datetime

    from contracts import AgentRun

    fields = {
        "id": "r1",
        "trigger": "drying.ranked",
        "tool_calls": [],
        "final_json": None,
        "model": "reasoning-primary",
        "prompt_version": "agent-v1",
        "started_at": datetime(2026, 10, 17, 12, 0, tzinfo=UTC),
        "ms": 0,
    }
    return AgentRun(**{**fields, **overrides})


class FakeWarehouse:
    def __init__(self, rows_by_sql: Mapping[str, list[dict]] | None = None):
        self._rows_by_sql = dict(rows_by_sql or {})
        self.queries: list[tuple[str, dict[str, object]]] = []

    def query(self, sql: str, params: Mapping[str, object]) -> list[dict]:
        self.queries.append((sql, dict(params)))
        return [dict(row) for row in self._rows_by_sql.get(sql, [])]


def weekly_row(**overrides) -> dict:
    from datetime import date

    fields = {
        "cell_id": "riau-1-1",
        "region": "riau",
        "week_start": date(2026, 10, 12),
        "s1_anom_db": -4.2,
        "stale_s1": False,
        "rain_30d_mm": 180.0,
        "rain_deficit_pct": 0.31,
        "canal_dist_m": 140.0,
        "peat_class": 1,
        "drying_score": 90.5,
        "rank": 1,
        "lat": 0.5,
        "lon": 101.4,
    }
    return {**fields, **overrides}


def function_call(name: str, args: dict[str, object], call_id: str):
    from google.adk.models import LlmResponse

    part = types.Part(
        function_call=types.FunctionCall(id=call_id, name=name, args=args)
    )
    return LlmResponse(content=types.Content(role="model", parts=[part]))


def final_answer(text: str):
    from google.adk.models import LlmResponse

    return LlmResponse(
        content=types.Content(role="model", parts=[types.Part(text=text)])
    )


def make_fake_llm(model: str, script: list):
    from google.adk.models import BaseLlm, LlmCapabilities
    from pydantic import Field

    class FakeLlm(BaseLlm):
        outcomes: list
        contents: list = Field(default_factory=list)
        system_instructions: list = Field(default_factory=list)
        response_schemas: list = Field(default_factory=list)
        tool_names: list = Field(default_factory=list)

        @property
        def capabilities(self) -> LlmCapabilities:
            return LlmCapabilities(output_schema_and_tools=True)

        async def generate_content_async(self, llm_request, stream=False):
            self.contents.append(
                [c.model_copy(deep=True) for c in llm_request.contents]
            )
            self.system_instructions.append(llm_request.config.system_instruction)
            self.response_schemas.append(llm_request.config.response_schema)
            self.tool_names.append(sorted(llm_request.tools_dict))
            if not self.outcomes:
                raise AssertionError(f"{self.model} has no scripted response left")
            outcome = self.outcomes.pop(0)
            if isinstance(outcome, Exception):
                raise outcome
            yield outcome.model_copy(update={"model_version": self.model})

    return FakeLlm(model=model, outcomes=list(script))


def make_ranked_dam(**overrides):
    from contracts import GeoPoint, RankedDam

    fields = {
        "dam_id": "dam-1",
        "region": "riau",
        "cell_id": "riau-1-1",
        "point": GeoPoint(lat=0.5, lon=101.4),
        "last_state": "broken",
        "last_checked_at": None,
        "drying_score": 91.0,
        "rank": 1,
        "example": True,
    }
    return RankedDam(**{**fields, **overrides})


def make_drying_ranked_event(**overrides):
    from datetime import UTC, datetime

    from contracts import DryingRanked, DryingRankedEvent

    fields = {
        "id": "evt-1",
        "occurred_at": datetime(2026, 10, 17, 12, 0, tzinfo=UTC),
        "region": "riau",
        "example": True,
        "type": "drying.ranked",
        "payload": DryingRanked(
            region="riau", week="2026-W42", top_cells=[], top_dams=[]
        ),
    }
    return DryingRankedEvent(**{**fields, **overrides})


def push_body(event, message_id: str = "m-1") -> dict:
    import base64

    data = base64.b64encode(event.model_dump_json().encode()).decode()
    return {
        "message": {"data": data, "messageId": message_id, "attributes": {}},
        "subscription": "projects/p/subscriptions/s",
    }
