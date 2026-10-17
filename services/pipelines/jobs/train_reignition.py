import argparse
import os
import sys
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime

from adapters import reignition_model
from adapters.bigquery import Warehouse
from domain.reignition_eval import (
    EVAL_SPLITS,
    VARIANTS,
    EmptyRanking,
    EvalRecord,
    ModelVariant,
    baseline_record,
    empty_eval_splits,
    model_record,
)
from ee_lib.config import load_region
from jobs.cli import (
    DATASET,
    JobError,
    configure_logging,
    full_flow_region,
    logger,
    query_report,
    resolve_config_dir,
    resolve_project,
    run_job,
)


def first_row(rows: Sequence[Mapping[str, object]], step: str) -> Mapping[str, object]:
    if not rows:
        raise JobError(f"{step} returned no row")
    return rows[0]


def require_labeled_eval_splits(
    warehouse: Warehouse, region_id: str, queries: list[dict[str, object]]
) -> None:
    counted = reignition_model.count_labeled(warehouse, region_id)
    queries.append(query_report("count_labeled", counted))
    empty = empty_eval_splits(first_row(counted.rows, "labeled count"))
    if empty:
        raise JobError(
            f"no labeled events in split {', '.join(empty)} for {region_id}; "
            "run jobs.reignition_features first"
        )


def evaluate_variant(
    warehouse: Warehouse,
    variant: ModelVariant,
    region_id: str,
    evaluated_at: datetime,
    queries: list[dict[str, object]],
) -> list[EvalRecord]:
    explain = reignition_model.global_explain(warehouse, variant)
    queries.append(query_report(f"explain_{variant.name}", explain))
    records: list[EvalRecord] = []
    for split in EVAL_SPLITS:
        evaluated = reignition_model.evaluate(warehouse, variant, region_id, split)
        queries.append(query_report(f"evaluate_{variant.name}_{split}", evaluated))
        predicted = reignition_model.predict_labeled(
            warehouse, variant, region_id, split
        )
        queries.append(query_report(f"predict_{variant.name}_{split}", predicted))
        records.append(
            model_record(
                variant=variant,
                region=region_id,
                split=split,
                evaluation=first_row(evaluated.rows, f"ML.EVALUATE {split}"),
                predictions=predicted.rows,
                explain=explain.rows,
                evaluated_at=evaluated_at,
            )
        )
        if variant.with_baseline:
            records.append(
                baseline_record(
                    region=region_id,
                    split=split,
                    predictions=predicted.rows,
                    evaluated_at=evaluated_at,
                )
            )
    return records


def record_summary(record: EvalRecord) -> dict[str, object]:
    return {
        "model": record.model,
        "split": record.split,
        "events": record.events,
        "positives": record.positives,
        "auc": record.auc,
        "precision_top10": record.precision_top10,
        "recall_top10": record.recall_top10,
        "log_loss": record.log_loss,
    }


def train_reignition(
    *,
    region_id: str,
    warehouse: Warehouse,
    evaluated_at: datetime,
    dry_run: bool,
) -> dict[str, object]:
    queries: list[dict[str, object]] = []
    for variant in VARIANTS:
        estimate = reignition_model.estimate_training(warehouse, variant, region_id)
        queries.append(query_report(f"estimate_{variant.name}", estimate))
    summary: dict[str, object] = {"region": region_id, "dry_run": dry_run}
    if dry_run:
        return {**summary, "queries": queries}
    require_labeled_eval_splits(warehouse, region_id, queries)
    records: list[EvalRecord] = []
    for variant in VARIANTS:
        trained = reignition_model.train(warehouse, variant, region_id)
        queries.append(query_report(f"train_{variant.name}", trained))
        try:
            records.extend(
                evaluate_variant(warehouse, variant, region_id, evaluated_at, queries)
            )
        except EmptyRanking as error:
            raise JobError(f"{variant.name}: {error}") from error
    reignition_model.append_eval(warehouse, records)
    return {
        **summary,
        "evaluations": [record_summary(record) for record in records],
        "bytes_billed": sum(
            int(str(query["bytes"])) for query in queries if not query["estimate"]
        ),
        "queries": queries,
    }


def parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m jobs.train_reignition",
        description="Train bara.reignition_v1 (registered to Vertex AI) and the "
        "variant without rain_7d_after on bara.reignition_training, then write "
        "ML.EVALUATE and the detection_days baseline to bara.eval_reignition.",
    )
    parser.add_argument(
        "--region", required=True, help="region id in config/regions.yaml"
    )
    parser.add_argument(
        "--project", help="Google Cloud project (default: GOOGLE_CLOUD_PROJECT)"
    )
    parser.add_argument(
        "--config-dir",
        help="config directory (default: BARA_CONFIG_DIR or repo config/)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="estimate the training input scan; train and write nothing",
    )
    return parser.parse_args(argv)


def main(
    argv: Sequence[str] | None = None, environ: Mapping[str, str] = os.environ
) -> int:
    args = parse_args(argv)

    def work() -> dict[str, object]:
        project = resolve_project(args.project, environ)
        region = load_region(resolve_config_dir(args.config_dir, environ), args.region)
        region_id = full_flow_region(region)
        from google.cloud import bigquery

        logger.info("%s: training on bara.reignition_training", region_id)
        return train_reignition(
            region_id=region_id,
            warehouse=Warehouse(bigquery.Client(project=project), project, DATASET),
            evaluated_at=datetime.now(UTC),
            dry_run=args.dry_run,
        )

    return run_job(work)


if __name__ == "__main__":
    configure_logging()
    sys.exit(main())
