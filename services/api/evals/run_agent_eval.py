import json
import sys
import time
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from google.adk.cli.cli_tools_click import main as adk_cli
from google.adk.evaluation.eval_case import (
    Invocation,
    InvocationEvents,
    get_all_tool_calls,
)
from google.adk.evaluation.eval_result import EvalCaseResult, EvalSetResult
from google.adk.evaluation.evaluator import EvalStatus

from evals.agent_eval.eval_set import EVAL_SET_PATH, EVALS_DIR, build_eval_set

AGENT_DIR = EVALS_DIR / "bara_eval"
CONFIG_PATH = EVALS_DIR / "test_config.json"
HISTORY_DIR = AGENT_DIR / ".adk" / "eval_history"
REPO_ROOT = EVALS_DIR.parents[2]
OUTPUT_PATH = REPO_ROOT / "docs" / "eval" / "agent.json"
RESULT_SUFFIX = ".evalset_result.json"


class EvalRunMissing(Exception):
    pass


def run_adk_eval() -> None:
    adk_cli(
        args=[
            "eval",
            str(AGENT_DIR),
            str(EVAL_SET_PATH),
            "--config_file_path",
            str(CONFIG_PATH),
        ],
        standalone_mode=False,
    )


def newest_result(history_dir: Path, since: float) -> EvalSetResult:
    fresh = [
        path
        for path in history_dir.glob(f"*{RESULT_SUFFIX}")
        if path.stat().st_mtime >= since
    ]
    if not fresh:
        raise EvalRunMissing(f"no eval result written to {history_dir}")
    newest = max(fresh, key=lambda path: path.stat().st_mtime)
    return EvalSetResult.model_validate_json(newest.read_text(encoding="utf-8"))


def actual_invocations(case: EvalCaseResult) -> list[Invocation]:
    return [item.actual_invocation for item in case.eval_metric_result_per_invocation]


def invocation_models(invocation: Invocation) -> set[str]:
    data = invocation.intermediate_data
    if not isinstance(data, InvocationEvents):
        return set()
    return {
        event.model_version
        for event in data.invocation_events
        if event.model_version is not None
    }


def models_used(result: EvalSetResult) -> str:
    models = {
        model
        for case in result.eval_case_results
        for invocation in actual_invocations(case)
        for model in invocation_models(invocation)
    }
    if not models:
        raise EvalRunMissing("the eval result names no model version")
    return ", ".join(sorted(models))


def case_passed(case: EvalCaseResult) -> bool:
    return case.final_eval_status == EvalStatus.PASSED


def ordered_results(
    result: EvalSetResult, case_ids: Sequence[str]
) -> list[dict[str, object]]:
    by_id = {case.eval_id: case for case in result.eval_case_results}
    missing = [case_id for case_id in case_ids if case_id not in by_id]
    if missing:
        raise EvalRunMissing(f"no result for {', '.join(missing)}")
    return [
        {"case": case_id, "passed": case_passed(by_id[case_id])} for case_id in case_ids
    ]


def summarize(
    result: EvalSetResult, case_ids: Sequence[str], run_at: datetime
) -> dict[str, object]:
    results = ordered_results(result, case_ids)
    passed = len([item for item in results if item["passed"]])
    return {
        "run_at": run_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "model": models_used(result),
        "cases": len(results),
        "passed": passed,
        "pass_rate": round(passed / len(results), 4),
        "results": results,
    }


def called_tools(case: EvalCaseResult) -> list[str]:
    return [
        str(call.name)
        for invocation in actual_invocations(case)
        for call in get_all_tool_calls(invocation.intermediate_data)
    ]


def report_line(case: EvalCaseResult) -> str:
    status = "PASS" if case_passed(case) else "FAIL"
    return f"{status} {case.eval_id}: {' -> '.join(called_tools(case)) or 'no tool'}"


def main() -> int:
    case_ids = [case.eval_id for case in build_eval_set().eval_cases]
    run_at = datetime.now(UTC)
    started = time.time()
    run_adk_eval()
    result = newest_result(HISTORY_DIR, started)
    summary = summarize(result, case_ids, run_at)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    for case in result.eval_case_results:
        sys.stdout.write(report_line(case) + "\n")
    sys.stdout.write(
        f"wrote {OUTPUT_PATH}: {summary['passed']}/{summary['cases']} passed, "
        f"model {summary['model']}, wall {time.time() - started:.0f} s\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
