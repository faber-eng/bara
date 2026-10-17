from collections.abc import Mapping, Sequence

from google.cloud.bigquery import SchemaField

from adapters.bigquery import Warehouse
from domain.evidence_eval import FIELDS

EVAL_EVIDENCE = "eval_evidence"

EVAL_EVIDENCE_SCHEMA = (
    SchemaField("run_at", "TIMESTAMP", mode="REQUIRED"),
    SchemaField("file", "STRING", mode="REQUIRED"),
    SchemaField("kind", "STRING", mode="REQUIRED"),
    SchemaField("model", "STRING", mode="REQUIRED"),
    SchemaField("prompt_version", "STRING", mode="REQUIRED"),
    SchemaField("latency_ms", "FLOAT64", mode="REQUIRED"),
    SchemaField("error", "STRING", mode="NULLABLE"),
    *(SchemaField(f"label_{field}", "STRING", mode="REQUIRED") for field in FIELDS),
    *(SchemaField(f"verdict_{field}", "STRING", mode="NULLABLE") for field in FIELDS),
)


def append_evidence_eval(
    warehouse: Warehouse, rows: Sequence[Mapping[str, object]]
) -> None:
    warehouse.append_rows(EVAL_EVIDENCE, EVAL_EVIDENCE_SCHEMA, rows)
