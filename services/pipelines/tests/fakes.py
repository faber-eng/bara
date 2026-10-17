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
