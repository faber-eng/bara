from collections.abc import Mapping, Sequence
from types import SimpleNamespace

from google.api_core.exceptions import NotFound


class FakeQueryJob:
    def __init__(self, rows: list[dict], bytes_billed: int, bytes_processed: int):
        self._rows = rows
        self.total_bytes_billed = bytes_billed
        self.total_bytes_processed = bytes_processed

    def result(self) -> list[dict]:
        return [dict(row) for row in self._rows]


class RecordingBigQueryClient:
    def __init__(
        self,
        responses: Mapping[str, Sequence[Mapping[str, object]]] | None = None,
        existing: Sequence[str] = (),
        bytes_billed: int = 10_485_760,
        bytes_processed: int = 52_428_800,
    ):
        self.queries: list[tuple[str, object]] = []
        self.loads: list[tuple[str, list[dict], object]] = []
        self.created: list[object] = []
        self.calls: list[str] = []
        self._responses = dict(responses or {})
        self._existing = set(existing)
        self._bytes_billed = bytes_billed
        self._bytes_processed = bytes_processed

    def query(self, sql, job_config=None):
        self.queries.append((sql, job_config))
        self.calls.append("query")
        return FakeQueryJob(
            self._rows_for(sql), self._bytes_billed, self._bytes_processed
        )

    def load_table_from_json(self, rows, destination, job_config=None):
        self.loads.append((destination, list(rows), job_config))
        self.calls.append("load")
        return SimpleNamespace(result=lambda: None)

    def get_table(self, table_id):
        if table_id.rsplit(".", 1)[-1] not in self._existing:
            raise NotFound(f"table {table_id} not found")
        return SimpleNamespace(table_id=table_id)

    def create_table(self, table, exists_ok=False):
        self.created.append(table)
        self.calls.append("create")
        return table

    def sql_sent(self) -> list[str]:
        return [sql for sql, _ in self.queries]

    def _rows_for(self, sql: str) -> list[dict]:
        for marker, rows in self._responses.items():
            if marker in sql:
                return [dict(row) for row in rows]
        return []


class FakeEarth:
    def __init__(self, peat_features=(), measurements=(), chirps_last=None):
        self.peat_features = list(peat_features)
        self.measurements = list(measurements)
        self.chirps_last = chirps_last
        self.calls: list[tuple[str, object]] = []

    def peat_cells(self, region, aoi):
        self.calls.append(("peat_cells", region.id))
        return list(self.peat_features)

    def chirps_last_day(self, before):
        self.calls.append(("chirps_last_day", before))
        return self.chirps_last

    def drying_inputs(self, region, aoi, cells_table, week_start, window):
        self.calls.append(("drying_inputs", (cells_table, week_start, window)))
        return list(self.measurements)


class FakeFireEarth:
    def __init__(self, features_by_year=None, firms_last=None):
        self.features_by_year = dict(features_by_year or {})
        self.firms_last = firms_last
        self.calls: list[tuple[str, object]] = []

    def firms_last_day(self, before):
        self.calls.append(("firms_last_day", before))
        return self.firms_last

    def fire_detections(self, aoi, buffer_m, start, end):
        self.calls.append(("fire_detections", (buffer_m, start, end)))
        return list(self.features_by_year.get(start.year, []))


class FakeFeatureEarth:
    def __init__(self, measures=(), peat=(), chirps_last=None):
        self.measures = list(measures)
        self.peat = list(peat)
        self.chirps_last = chirps_last
        self.calls: list[tuple[str, object]] = []

    def chirps_last_day(self, before):
        self.calls.append(("chirps_last_day", before))
        return self.chirps_last

    def reignition_measures(self, region, aoi, cells_table, dates):
        self.calls.append(("reignition_measures", (cells_table, dates)))
        return list(self.measures)

    def peat_fractions(self, region, cells_table):
        self.calls.append(("peat_fractions", cells_table))
        return list(self.peat)


class FakeDocumentRef:
    def __init__(self, store: dict, path: str, doc_id: str):
        self.store = store
        self.path = path
        self.id = doc_id

    @property
    def key(self) -> str:
        return f"{self.path}/{self.id}"


class FakeCollectionRef:
    def __init__(self, store: dict, path: str):
        self._store = store
        self._path = path

    def document(self, doc_id: str) -> FakeDocumentRef:
        return FakeDocumentRef(self._store, self._path, doc_id)

    def list_documents(self):
        prefix = f"{self._path}/"
        return [
            FakeDocumentRef(self._store, self._path, key[len(prefix) :])
            for key in list(self._store)
            if key.startswith(prefix) and "/" not in key[len(prefix) :]
        ]


class FakeBatch:
    def __init__(self, client: "FakeFirestore"):
        self._client = client
        self._ops: list[tuple[str, FakeDocumentRef, dict | None]] = []

    def set(self, ref: FakeDocumentRef, data: dict) -> None:
        self._ops.append(("set", ref, data))

    def delete(self, ref: FakeDocumentRef) -> None:
        self._ops.append(("delete", ref, None))

    def commit(self) -> None:
        self._client.commits.append([(op, ref.key) for op, ref, _ in self._ops])
        for op, ref, data in self._ops:
            if op == "set":
                self._client.docs[ref.key] = data
            else:
                self._client.docs.pop(ref.key, None)


class FakeFirestore:
    def __init__(self, docs: dict[str, dict] | None = None):
        self.docs: dict[str, dict] = dict(docs or {})
        self.commits: list[list[tuple[str, str]]] = []

    def collection(self, path: str) -> FakeCollectionRef:
        return FakeCollectionRef(self.docs, path)

    def batch(self) -> FakeBatch:
        return FakeBatch(self)


class FakePublishFuture:
    def __init__(self, message_id: str):
        self._message_id = message_id

    def result(self, timeout=None) -> str:
        return self._message_id


class FakePubSub:
    def __init__(self, message_id: str = "msg-1", log: list | None = None):
        self.published: list[tuple[str, bytes, dict]] = []
        self._message_id = message_id
        self._log = log if log is not None else []

    def topic_path(self, project: str, topic: str) -> str:
        return f"projects/{project}/topics/{topic}"

    def publish(self, path: str, data: bytes, **attributes):
        self._log.append("publish")
        self.published.append((path, data, attributes))
        return FakePublishFuture(self._message_id)
