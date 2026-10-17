import os
from datetime import UTC, date, datetime
from types import SimpleNamespace

import pytest
from google.cloud import bigquery

from adapters.bigquery import (
    MAX_BYTES_BILLED,
    InvalidTableName,
    Warehouse,
    WarehouseError,
)


class RecordingBigQueryClient:
    def __init__(self, rows=(), insert_errors=()):
        self.queries = []
        self.inserts = []
        self.loads = []
        self._rows = rows
        self._insert_errors = list(insert_errors)

    def query(self, sql, job_config=None):
        self.queries.append((sql, job_config))
        return SimpleNamespace(result=lambda: [dict(row) for row in self._rows])

    def insert_rows_json(self, table, rows):
        self.inserts.append((table, rows))
        return self._insert_errors

    def load_table_from_json(self, rows, table, job_config=None):
        self.loads.append((table, rows, job_config))
        return SimpleNamespace(result=lambda: None)


def make_warehouse(client=None):
    client = client or RecordingBigQueryClient()
    return Warehouse(client, project="p", dataset="bara"), client


def test_query_passes_values_as_query_parameters_and_sql_unchanged():
    warehouse, client = make_warehouse()
    sql = "SELECT * FROM bara.cells WHERE region = @region AND rank <= @top"

    warehouse.query(sql, {"region": "riau", "top": 10})

    sent_sql, config = client.queries[0]
    assert sent_sql == sql
    by_name = {p.name: p for p in config.query_parameters}
    assert by_name["region"].type_ == "STRING"
    assert by_name["region"].value == "riau"
    assert by_name["top"].type_ == "INT64"
    assert by_name["top"].value == 10


def test_a_hostile_value_never_reaches_the_sql_text():
    warehouse, client = make_warehouse()

    warehouse.query("SELECT 1 WHERE x = @x", {"x": "1; DROP TABLE bara.cells"})

    assert "DROP" not in client.queries[0][0]


def test_query_maps_python_types_to_bigquery_types():
    warehouse, client = make_warehouse()
    params = {
        "s": "a",
        "i": 1,
        "f": 1.5,
        "b": True,
        "d": date(2026, 10, 17),
        "t": datetime(2026, 10, 17, tzinfo=UTC),
    }

    warehouse.query("SELECT 1", params)

    types = {p.name: p.type_ for p in client.queries[0][1].query_parameters}
    assert types == {
        "s": "STRING",
        "i": "INT64",
        "f": "FLOAT64",
        "b": "BOOL",
        "d": "DATE",
        "t": "TIMESTAMP",
    }


def test_query_rejects_an_unsupported_parameter_type():
    warehouse, client = make_warehouse()

    with pytest.raises(TypeError):
        warehouse.query("SELECT 1", {"x": [1, 2]})

    assert client.queries == []


def test_query_caps_the_bytes_billed():
    warehouse, client = make_warehouse()

    warehouse.query("SELECT 1", {})

    assert client.queries[0][1].maximum_bytes_billed == MAX_BYTES_BILLED


def test_query_returns_rows_as_dicts():
    warehouse, _ = make_warehouse(RecordingBigQueryClient(rows=[{"one": 1}]))

    assert warehouse.query("SELECT 1 AS one", {}) == [{"one": 1}]


def test_insert_rows_targets_the_fully_qualified_table():
    warehouse, client = make_warehouse()

    warehouse.insert_rows("events", [{"a": 1}])

    assert client.inserts == [("p.bara.events", [{"a": 1}])]


def test_insert_rows_raises_when_bigquery_reports_row_errors():
    warehouse, _ = make_warehouse(
        RecordingBigQueryClient(insert_errors=[{"index": 0, "errors": ["bad"]}])
    )

    with pytest.raises(WarehouseError):
        warehouse.insert_rows("events", [{"a": 1}])


def test_insert_of_no_rows_makes_no_call():
    warehouse, client = make_warehouse()

    warehouse.insert_rows("events", [])

    assert client.inserts == []


@pytest.mark.parametrize("table", ["a.b", "x; drop", "", "1abc", "a-b"])
def test_insert_rejects_unsafe_table_names(table):
    warehouse, client = make_warehouse()

    with pytest.raises(InvalidTableName):
        warehouse.insert_rows(table, [{"a": 1}])

    assert client.inserts == []


@pytest.mark.live
def test_live_parameterised_query_runs():
    from google.cloud import bigquery

    project = os.environ["GOOGLE_CLOUD_PROJECT"]
    warehouse = Warehouse(bigquery.Client(project=project), project, "bara")

    assert warehouse.query("SELECT @x AS x", {"x": 1}) == [{"x": 1}]


def test_append_rows_loads_with_the_schema_and_appends():
    warehouse, client = make_warehouse()
    schema = [bigquery.SchemaField("file", "STRING", mode="REQUIRED")]

    warehouse.append_rows("eval_evidence", schema, [{"file": "a.jpg"}])

    [(table, rows, config)] = client.loads
    assert table == "p.bara.eval_evidence"
    assert rows == [{"file": "a.jpg"}]
    assert config.write_disposition == bigquery.WriteDisposition.WRITE_APPEND
    assert [field.name for field in config.schema] == ["file"]


def test_append_rows_refuses_a_bad_table_name_and_skips_no_rows():
    warehouse, client = make_warehouse()

    warehouse.append_rows("eval_evidence", [], [])
    with pytest.raises(InvalidTableName):
        warehouse.append_rows("bad name", [], [{"file": "a"}])

    assert client.loads == []
