from collections.abc import Iterable, Mapping
from dataclasses import dataclass

BATCH_LIMIT = 400
ROOT = "rankings"


@dataclass(frozen=True)
class ReplaceResult:
    written: int
    deleted: int


def chunks[T](items: list[T], size: int) -> Iterable[list[T]]:
    for start in range(0, len(items), size):
        yield items[start : start + size]


class RankingsStore:
    def __init__(self, client):
        self._client = client

    def replace(
        self, region: str, kind: str, documents: Mapping[str, Mapping[str, object]]
    ) -> ReplaceResult:
        collection = self._client.collection(f"{ROOT}/{region}/{kind}")
        stale = [ref for ref in collection.list_documents() if ref.id not in documents]
        for chunk in chunks(list(documents.items()), BATCH_LIMIT):
            batch = self._client.batch()
            for doc_id, data in chunk:
                batch.set(collection.document(doc_id), dict(data))
            batch.commit()
        for chunk in chunks(stale, BATCH_LIMIT):
            batch = self._client.batch()
            for ref in chunk:
                batch.delete(ref)
            batch.commit()
        return ReplaceResult(written=len(documents), deleted=len(stale))
