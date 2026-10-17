import re
from collections.abc import Mapping, Sequence
from datetime import date, datetime

from google.cloud import bigquery

DATASET = "bara"
MAX_BYTES_BILLED = 1_000_000_000
TABLE_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class WarehouseError(Exception):
    pass


class InvalidTableName(Exception):
    pass


def bigquery_type(value: object) -> str:
    if isinstance(value, bool):
        return "BOOL"
    if isinstance(value, int):
        return "INT64"
    if isinstance(value, float):
        return "FLOAT64"
    if isinstance(value, str):
        return "STRING"
    if isinstance(value, datetime):
        return "TIMESTAMP"
    if isinstance(value, date):
        return "DATE"
    raise TypeError(f"unsupported query parameter type: {type(value).__name__}")


def build_parameters(
    params: Mapping[str, object],
) -> list[bigquery.ScalarQueryParameter]:
    return [
        bigquery.ScalarQueryParameter(name, bigquery_type(value), value)
        for name, value in params.items()
    ]


class Warehouse:
    def __init__(self, client, project: str, dataset: str):
        self._client = client
        self._project = project
        self._dataset = dataset

    def insert_rows(self, table: str, rows: Sequence[Mapping[str, object]]) -> None:
        if not TABLE_NAME.match(table):
            raise InvalidTableName(f"invalid table name: {table!r}")
        if not rows:
            return
        table_id = f"{self._project}.{self._dataset}.{table}"
        errors = self._client.insert_rows_json(table_id, list(rows))
        if errors:
            raise WarehouseError(f"insert into {table_id} failed: {errors}")

    def query(self, sql: str, params: Mapping[str, object]) -> list[dict]:
        config = bigquery.QueryJobConfig(
            query_parameters=build_parameters(params),
            maximum_bytes_billed=MAX_BYTES_BILLED,
        )
        job = self._client.query(sql, job_config=config)
        return [dict(row) for row in job.result()]
