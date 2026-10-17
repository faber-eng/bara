from collections.abc import Sequence
from dataclasses import asdict

from google.cloud.bigquery import SchemaField

from adapters.bigquery import QueryResult, TableSpec, Warehouse
from domain.reignition_eval import (
    EVAL_SPLITS,
    EvalRecord,
    ModelVariant,
    feature_exclusions,
)

MAX_ITERATIONS = 20

EVAL_REIGNITION = TableSpec(
    name="eval_reignition",
    schema=(
        SchemaField("evaluated_at", "TIMESTAMP", mode="REQUIRED"),
        SchemaField("region", "STRING", mode="REQUIRED"),
        SchemaField("model", "STRING", mode="REQUIRED"),
        SchemaField("split", "STRING", mode="REQUIRED"),
        SchemaField("events", "INT64", mode="REQUIRED"),
        SchemaField("positives", "INT64", mode="REQUIRED"),
        SchemaField("auc", "FLOAT64", mode="NULLABLE"),
        SchemaField("ml_evaluate_auc", "FLOAT64", mode="NULLABLE"),
        SchemaField("precision_top10", "FLOAT64", mode="REQUIRED"),
        SchemaField("recall_top10", "FLOAT64", mode="NULLABLE"),
        SchemaField("log_loss", "FLOAT64", mode="NULLABLE"),
        SchemaField(
            "global_explain",
            "RECORD",
            mode="REPEATED",
            fields=(
                SchemaField("feature", "STRING", mode="REQUIRED"),
                SchemaField("attribution", "FLOAT64", mode="REQUIRED"),
            ),
        ),
    ),
    partition_field=None,
    clustering=("region", "model"),
)

TRAINING_SELECT = """
SELECT * EXCEPT({excluded}), split = 'valid' AS is_eval
FROM reignition_training
WHERE region = @region AND split IN ('train', 'valid') AND reignited IS NOT NULL
"""

TRAIN_SQL = """
CREATE OR REPLACE MODEL `{model}`
TRANSFORM (
  * EXCEPT (month, peat_class),
  CAST(month AS STRING) AS month,
  CAST(peat_class AS STRING) AS peat_class
)
OPTIONS (
  model_type = 'LOGISTIC_REG',
  input_label_cols = ['reignited'],
  data_split_method = 'CUSTOM',
  data_split_col = 'is_eval',
  auto_class_weights = TRUE,
  enable_global_explain = TRUE,
  max_iterations = {max_iterations}{registry}
) AS
{select}
"""

REGISTRY_OPTIONS = """,
  model_registry = 'VERTEX_AI',
  vertex_ai_model_id = '{vertex_model_id}'"""

LABELED_COUNT_SQL = """
SELECT {counts}
FROM reignition_training
WHERE region = @region AND reignited IS NOT NULL
"""

LABELED_SPLIT = """
SELECT * EXCEPT({excluded})
FROM reignition_training
WHERE region = @region AND split = @split AND reignited IS NOT NULL
"""

LABELED_ROWS = """
SELECT *
FROM reignition_training
WHERE region = @region AND split = @split AND reignited IS NOT NULL
"""

EVALUATE_SQL = """
SELECT roc_auc, log_loss
FROM ML.EVALUATE(MODEL `{model}`, ({rows}))
"""

PREDICT_SQL = """
SELECT
  event_id,
  reignited,
  detection_days,
  (SELECT prob FROM UNNEST(predicted_reignited_probs) WHERE label = 1) AS p_reignite
FROM ML.PREDICT(MODEL `{model}`, ({rows}))
"""

GLOBAL_EXPLAIN_SQL = """
SELECT feature, attribution
FROM ML.GLOBAL_EXPLAIN(MODEL `{model}`)
ORDER BY attribution DESC
"""


def excluded(variant: ModelVariant) -> str:
    return ", ".join(feature_exclusions(variant))


def count_labeled(warehouse: Warehouse, region: str) -> QueryResult:
    counts = ", ".join(
        f"COUNTIF(split = '{split}') AS {split}" for split in EVAL_SPLITS
    )
    return warehouse.query(LABELED_COUNT_SQL.format(counts=counts), {"region": region})


def registry(variant: ModelVariant) -> str:
    if variant.vertex_model_id is None:
        return ""
    return REGISTRY_OPTIONS.format(vertex_model_id=variant.vertex_model_id)


def model_id(warehouse: Warehouse, variant: ModelVariant) -> str:
    return warehouse.table_id(variant.name)


def training_select(variant: ModelVariant) -> str:
    return TRAINING_SELECT.format(excluded=excluded(variant))


def estimate_training(
    warehouse: Warehouse, variant: ModelVariant, region: str
) -> QueryResult:
    return warehouse.query(training_select(variant), {"region": region}, dry_run=True)


def train(warehouse: Warehouse, variant: ModelVariant, region: str) -> QueryResult:
    sql = TRAIN_SQL.format(
        model=model_id(warehouse, variant),
        max_iterations=MAX_ITERATIONS,
        registry=registry(variant),
        select=training_select(variant),
    )
    return warehouse.query(sql, {"region": region})


def labeled_rows(variant: ModelVariant) -> str:
    return LABELED_SPLIT.format(excluded=excluded(variant))


def evaluate(
    warehouse: Warehouse, variant: ModelVariant, region: str, split: str
) -> QueryResult:
    sql = EVALUATE_SQL.format(
        model=model_id(warehouse, variant), rows=labeled_rows(variant)
    )
    return warehouse.query(sql, {"region": region, "split": split})


def predict_labeled(
    warehouse: Warehouse, variant: ModelVariant, region: str, split: str
) -> QueryResult:
    sql = PREDICT_SQL.format(model=model_id(warehouse, variant), rows=LABELED_ROWS)
    return warehouse.query(sql, {"region": region, "split": split})


def global_explain(warehouse: Warehouse, variant: ModelVariant) -> QueryResult:
    sql = GLOBAL_EXPLAIN_SQL.format(model=model_id(warehouse, variant))
    return warehouse.query(sql, {})


def eval_row(record: EvalRecord) -> dict[str, object]:
    return {
        **asdict(record),
        "evaluated_at": record.evaluated_at.isoformat(),
        "global_explain": [asdict(item) for item in record.global_explain],
    }


def append_eval(warehouse: Warehouse, records: Sequence[EvalRecord]) -> None:
    warehouse.ensure_table(EVAL_REIGNITION)
    warehouse.load_rows(
        EVAL_REIGNITION, [eval_row(record) for record in records], write="append"
    )
