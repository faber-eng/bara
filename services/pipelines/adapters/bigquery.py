import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal

from google.api_core.exceptions import NotFound
from google.cloud import bigquery

MAX_BYTES_BILLED = 1_000_000_000
TABLE_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

WriteMode = Literal["truncate", "append"]
WRITE_DISPOSITIONS: dict[WriteMode, str] = {
    "truncate": bigquery.WriteDisposition.WRITE_TRUNCATE,
    "append": bigquery.WriteDisposition.WRITE_APPEND,
}


REWRITE_REGION_SQL = """
BEGIN TRANSACTION;
DELETE FROM {table} WHERE region = @region;
INSERT INTO {table} SELECT * FROM {staging} WHERE region = @region;
COMMIT TRANSACTION;
"""


class InvalidTableName(Exception):
    pass


@dataclass(frozen=True)
class TableSpec:
    name: str
    schema: tuple[bigquery.SchemaField, ...]
    partition_field: str | None
    clustering: tuple[str, ...]


@dataclass(frozen=True)
class QueryResult:
    rows: list[dict]
    bytes_billed: int
    dry_run: bool


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


def staging_spec(spec: TableSpec) -> TableSpec:
    return TableSpec(
        name=f"{spec.name}_staging",
        schema=spec.schema,
        partition_field=None,
        clustering=(),
    )


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

    def table_id(self, name: str) -> str:
        if not TABLE_NAME.match(name):
            raise InvalidTableName(f"invalid table name: {name!r}")
        return f"{self._project}.{self._dataset}.{name}"

    def query(
        self,
        sql: str,
        params: Mapping[str, object],
        *,
        max_bytes_billed: int = MAX_BYTES_BILLED,
        dry_run: bool = False,
    ) -> QueryResult:
        config = bigquery.QueryJobConfig(
            query_parameters=build_parameters(params),
            maximum_bytes_billed=max_bytes_billed,
            default_dataset=f"{self._project}.{self._dataset}",
            dry_run=dry_run,
            use_query_cache=not dry_run,
        )
        job = self._client.query(sql, job_config=config)
        if dry_run:
            return QueryResult([], job.total_bytes_processed or 0, True)
        rows = [dict(row) for row in job.result()]
        return QueryResult(rows, job.total_bytes_billed or 0, False)

    def load_rows(
        self, spec: TableSpec, rows: Sequence[Mapping[str, object]], write: WriteMode
    ) -> None:
        config = bigquery.LoadJobConfig(
            schema=list(spec.schema),
            write_disposition=WRITE_DISPOSITIONS[write],
            source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
        )
        job = self._client.load_table_from_json(
            list(rows), self.table_id(spec.name), job_config=config
        )
        job.result()

    def table_exists(self, name: str) -> bool:
        try:
            self._client.get_table(self.table_id(name))
        except NotFound:
            return False
        return True

    def ensure_table(self, spec: TableSpec) -> None:
        table = bigquery.Table(self.table_id(spec.name), schema=list(spec.schema))
        if spec.partition_field is not None:
            table.time_partitioning = bigquery.TimePartitioning(
                type_=bigquery.TimePartitioningType.DAY, field=spec.partition_field
            )
        if spec.clustering:
            table.clustering_fields = list(spec.clustering)
        self._client.create_table(table, exists_ok=True)

    def rewrite_region(
        self, spec: TableSpec, region: str, rows: Sequence[Mapping[str, object]]
    ) -> QueryResult:
        staging = staging_spec(spec)
        self.table_id(spec.name)
        self.table_id(staging.name)
        self.ensure_table(spec)
        self.load_rows(staging, rows, write="truncate")
        sql = REWRITE_REGION_SQL.format(table=spec.name, staging=staging.name)
        return self.query(sql, {"region": region})
