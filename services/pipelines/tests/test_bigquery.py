from datetime import date

import pytest
from google.cloud import bigquery

from adapters.bigquery import (
    MAX_BYTES_BILLED,
    InvalidTableName,
    TableSpec,
    Warehouse,
)
from tests.fakes import RecordingBigQueryClient

SPEC = TableSpec(
    name="cell_weekly_drying",
    schema=(
        bigquery.SchemaField("cell_id", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("week_start", "DATE", mode="REQUIRED"),
    ),
    partition_field="week_start",
    clustering=("region", "cell_id"),
)


def make_warehouse(client=None):
    client = client or RecordingBigQueryClient()
    return Warehouse(client, project="p", dataset="bara"), client


def test_query_sends_values_as_parameters_against_the_bara_dataset():
    warehouse, client = make_warehouse()
    sql = "SELECT * FROM cells WHERE region = @region AND week_start = @week"

    warehouse.query(sql, {"region": "riau", "week": date(2026, 10, 12)})

    sent_sql, config = client.queries[0]
    assert sent_sql == sql
    types = {p.name: (p.type_, p.value) for p in config.query_parameters}
    assert types == {"region": ("STRING", "riau"), "week": ("DATE", date(2026, 10, 12))}
    assert config.default_dataset.dataset_id == "bara"
    assert config.default_dataset.project == "p"


def test_query_caps_bytes_billed_at_one_gigabyte_by_default():
    warehouse, client = make_warehouse()

    warehouse.query("SELECT 1", {})

    assert (
        client.queries[0][1].maximum_bytes_billed == MAX_BYTES_BILLED == 1_000_000_000
    )


def test_query_takes_a_larger_cap_when_asked():
    warehouse, client = make_warehouse()

    warehouse.query("SELECT 1", {}, max_bytes_billed=110_000_000_000)

    assert client.queries[0][1].maximum_bytes_billed == 110_000_000_000


def test_query_returns_rows_and_bytes_billed():
    client = RecordingBigQueryClient(responses={"SELECT": [{"one": 1}]}, bytes_billed=7)
    warehouse, _ = make_warehouse(client)

    result = warehouse.query("SELECT 1 AS one", {})

    assert result.rows == [{"one": 1}]
    assert result.bytes_billed == 7
    assert result.dry_run is False


def test_a_dry_run_reports_bytes_processed_and_returns_no_rows():
    client = RecordingBigQueryClient(
        responses={"SELECT": [{"one": 1}]}, bytes_processed=99
    )
    warehouse, _ = make_warehouse(client)

    result = warehouse.query("SELECT 1 AS one", {}, dry_run=True)

    config = client.queries[0][1]
    assert config.dry_run is True
    assert config.maximum_bytes_billed == MAX_BYTES_BILLED
    assert result.rows == []
    assert result.bytes_billed == 99
    assert result.dry_run is True


def test_query_rejects_an_unsupported_parameter_type():
    warehouse, client = make_warehouse()

    with pytest.raises(TypeError):
        warehouse.query("SELECT 1", {"x": [1, 2]})

    assert client.queries == []


def test_load_rows_truncates_with_the_spec_schema():
    warehouse, client = make_warehouse()

    warehouse.load_rows(SPEC, [{"cell_id": "a"}], write="truncate")

    table_id, rows, config = client.loads[0]
    assert table_id == "p.bara.cell_weekly_drying"
    assert rows == [{"cell_id": "a"}]
    assert config.write_disposition == "WRITE_TRUNCATE"
    assert [field.name for field in config.schema] == ["cell_id", "week_start"]


def test_load_rows_appends_when_asked():
    warehouse, client = make_warehouse()

    warehouse.load_rows(SPEC, [{"cell_id": "a"}], write="append")

    assert client.loads[0][2].write_disposition == "WRITE_APPEND"


def test_ensure_table_creates_a_partitioned_clustered_table_if_absent():
    warehouse, client = make_warehouse()

    warehouse.ensure_table(SPEC)

    table = client.created[0]
    assert table.table_id == "cell_weekly_drying"
    assert table.time_partitioning.field == "week_start"
    assert table.clustering_fields == ["region", "cell_id"]


def test_table_exists_reflects_get_table():
    warehouse, _ = make_warehouse(RecordingBigQueryClient(existing=["osm_canals"]))

    assert warehouse.table_exists("osm_canals") is True
    assert warehouse.table_exists("cells") is False


@pytest.mark.parametrize("name", ["a.b", "x; drop", "", "1abc", "a-b"])
def test_unsafe_table_names_are_rejected(name):
    warehouse, _ = make_warehouse()

    with pytest.raises(InvalidTableName):
        warehouse.table_id(name)


def test_rewrite_region_loads_staging_then_swaps_the_region_in_one_transaction():
    warehouse, client = make_warehouse()

    warehouse.rewrite_region(SPEC, "riau", [{"cell_id": "riau-1-1"}])

    destination, rows, config = client.loads[0]
    assert destination == "p.bara.cell_weekly_drying_staging"
    assert rows == [{"cell_id": "riau-1-1"}]
    assert config.write_disposition == "WRITE_TRUNCATE"
    sql, query_config = client.queries[0]
    assert "BEGIN TRANSACTION;" in sql
    assert "DELETE FROM cell_weekly_drying WHERE region = @region;" in sql
    assert (
        "INSERT INTO cell_weekly_drying SELECT * FROM cell_weekly_drying_staging" in sql
    )
    assert {p.name: p.value for p in query_config.query_parameters} == {
        "region": "riau"
    }
    assert client.calls == ["create", "load", "query"]
