import operator
from collections.abc import Callable, Mapping
from types import SimpleNamespace

from google.api_core import exceptions as gax
from google.genai import errors, types

from adapters.store import DocumentNotFound, Filter
from auth import InvalidToken
from contracts import ClockSettings, Contract


def api_error(code: int) -> errors.APIError:
    return errors.APIError(code, {"error": {"code": code, "message": f"status {code}"}})


class FakeModels:
    def __init__(self, outcomes: list[types.GenerateContentResponse | Exception]):
        self._outcomes = list(outcomes)
        self.calls: list[str] = []

    async def generate_content(
        self,
        *,
        model: str,
        contents: types.ContentListUnion,
        config: types.GenerateContentConfigOrDict | None = None,
    ) -> types.GenerateContentResponse:
        self.calls.append(model)
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

    def where(self, *filters: Filter) -> list[T]:
        return [
            item for item in self._documents.values() if matches(dict(item), filters)
        ]


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

    def set(self, data: dict[str, object]) -> None:
        self._store[self._doc_id] = dict(data)

    def create(self, data: dict[str, object]) -> None:
        if self._doc_id in self._store:
            raise gax.AlreadyExists("document exists")
        self._store[self._doc_id] = dict(data)

    def update(self, fields: Mapping[str, object]) -> None:
        if self._doc_id not in self._store:
            raise gax.NotFound("document missing")
        self._store[self._doc_id].update(fields)


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
    }
    return Case(**{**fields, **overrides})
