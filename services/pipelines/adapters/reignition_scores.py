from collections.abc import Sequence
from datetime import date, datetime

from google.cloud.bigquery import SchemaField

from adapters.bigquery import QueryResult, Since, TableSpec, Warehouse
from domain.reignition_scores import TOP_FEATURES, EventScore

REIGNITION_SCORES = TableSpec(
    name="reignition_scores",
    schema=(
        SchemaField("event_id", "STRING", mode="REQUIRED"),
        SchemaField("cell_id", "STRING", mode="REQUIRED"),
        SchemaField("region", "STRING", mode="REQUIRED"),
        SchemaField("quiet_date", "DATE", mode="REQUIRED"),
        SchemaField("model", "STRING", mode="REQUIRED"),
        SchemaField("p_reignite", "FLOAT64", mode="REQUIRED"),
        SchemaField(
            "top_features",
            "RECORD",
            mode="REPEATED",
            fields=(
                SchemaField("feature", "STRING", mode="REQUIRED"),
                SchemaField("attribution", "FLOAT64", mode="REQUIRED"),
            ),
        ),
        SchemaField("scored_at", "TIMESTAMP", mode="REQUIRED"),
    ),
    partition_field=None,
    clustering=("region", "cell_id"),
)

EXPLAIN_SQL = """
SELECT
  event_id,
  cell_id,
  region,
  quiet_date,
  IF(predicted_reignited = 1, probability, 1 - probability) AS p_reignite,
  top_feature_attributions
FROM ML.EXPLAIN_PREDICT(
  MODEL `{model}`,
  (
    SELECT *
    FROM reignition_training
    WHERE region = @region AND quiet_date >= @since
  ),
  STRUCT({top_k} AS top_k_features)
)
"""


def explain_scores(
    warehouse: Warehouse, model: str, region: str, since: date
) -> QueryResult:
    sql = EXPLAIN_SQL.format(model=warehouse.table_id(model), top_k=TOP_FEATURES)
    return warehouse.query(sql, {"region": region, "since": since})


def score_row(score: EventScore, model: str, scored_at: datetime) -> dict[str, object]:
    return {
        "event_id": score.event_id,
        "cell_id": score.cell_id,
        "region": score.region,
        "quiet_date": score.quiet_date.isoformat(),
        "model": model,
        "p_reignite": score.p_reignite,
        "top_features": [
            {"feature": item.feature, "attribution": item.attribution}
            for item in score.top_features
        ],
        "scored_at": scored_at.isoformat(),
    }


def replace_scores(
    warehouse: Warehouse,
    region: str,
    since: date,
    scores: Sequence[EventScore],
    model: str,
    scored_at: datetime,
) -> QueryResult:
    return warehouse.rewrite_region(
        REIGNITION_SCORES,
        region,
        [score_row(score, model, scored_at) for score in scores],
        Since("quiet_date", since),
    )
