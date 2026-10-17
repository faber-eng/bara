from collections.abc import Iterable, Mapping
from typing import Literal, NamedTuple, Protocol

from google.api_core import exceptions as gax
from google.cloud.firestore_v1 import Increment
from google.cloud.firestore_v1.base_query import FieldFilter

from contracts import Contract

BATCH_LIMIT = 400

FilterOp = Literal["==", "<", "<=", ">", ">=", "in"]


class DocumentNotFound(Exception):
    pass


class Filter(NamedTuple):
    field: str
    op: FilterOp
    value: object


class Collection[T: Contract](Protocol):
    def get(self, doc_id: str) -> T | None: ...

    def put(self, doc_id: str, item: T) -> None: ...

    def create_if_absent(self, doc_id: str, item: T) -> bool: ...

    def update(self, doc_id: str, fields: Mapping[str, object]) -> None: ...

    def add(
        self, doc_id: str, field: str, amount: int, fields: Mapping[str, object]
    ) -> None: ...

    def where(self, *filters: Filter) -> list[T]: ...

    def delete_many(self, doc_ids: Iterable[str]) -> None: ...

    def put_many(self, items: Mapping[str, T]) -> None: ...


class FirestoreCollection[T: Contract]:
    def __init__(self, client, name: str, model: type[T]):
        self._client = client
        self._name = name
        self._model = model

    def get(self, doc_id: str) -> T | None:
        snapshot = self._document(doc_id).get()
        if not snapshot.exists:
            return None
        return self._model.model_validate(snapshot.to_dict())

    def put(self, doc_id: str, item: T) -> None:
        self._document(doc_id).set(item.model_dump())

    def create_if_absent(self, doc_id: str, item: T) -> bool:
        try:
            self._document(doc_id).create(item.model_dump())
        except gax.AlreadyExists:
            return False
        return True

    def update(self, doc_id: str, fields: Mapping[str, object]) -> None:
        try:
            self._document(doc_id).update(dict(fields))
        except gax.NotFound as error:
            raise DocumentNotFound(f"{self._name}/{doc_id}") from error

    def add(
        self, doc_id: str, field: str, amount: int, fields: Mapping[str, object]
    ) -> None:
        data = {**fields, field: Increment(amount)}
        self._document(doc_id).set(data, merge=True)

    def where(self, *filters: Filter) -> list[T]:
        query = self._client.collection(self._name)
        for item in filters:
            query = query.where(filter=FieldFilter(item.field, item.op, item.value))
        return [self._model.model_validate(s.to_dict()) for s in query.stream()]

    def put_many(self, items: Mapping[str, T]) -> None:
        pending = list(items.items())
        for start in range(0, len(pending), BATCH_LIMIT):
            batch = self._client.batch()
            for doc_id, item in pending[start : start + BATCH_LIMIT]:
                batch.set(self._document(doc_id), item.model_dump())
            batch.commit()

    def delete_many(self, doc_ids: Iterable[str]) -> None:
        pending = list(doc_ids)
        for start in range(0, len(pending), BATCH_LIMIT):
            batch = self._client.batch()
            for doc_id in pending[start : start + BATCH_LIMIT]:
                batch.delete(self._document(doc_id))
            batch.commit()

    def _document(self, doc_id: str):
        return self._client.collection(self._name).document(doc_id)
