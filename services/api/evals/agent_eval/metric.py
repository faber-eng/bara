from collections.abc import Sequence

from google.adk.evaluation.eval_case import (
    ConversationScenario,
    Invocation,
    get_all_tool_calls,
)
from google.adk.evaluation.eval_metrics import EvalMetric
from google.adk.evaluation.evaluator import (
    EvalStatus,
    EvaluationResult,
    PerInvocationResult,
)
from google.genai import types


def args_match(actual: types.FunctionCall, expected: types.FunctionCall) -> bool:
    actual_args = actual.args or {}
    expected_args = expected.args or {}
    return all(
        key in actual_args and actual_args[key] == value
        for key, value in expected_args.items()
    )


def call_matches(actual: types.FunctionCall, expected: types.FunctionCall) -> bool:
    return actual.name == expected.name and args_match(actual, expected)


def trajectory_matches(
    actual: Sequence[types.FunctionCall], expected: Sequence[types.FunctionCall]
) -> bool:
    if len(actual) != len(expected):
        return False
    return all(
        call_matches(left, right) for left, right in zip(actual, expected, strict=True)
    )


def status_for(passed: bool) -> EvalStatus:
    if passed:
        return EvalStatus.PASSED
    return EvalStatus.FAILED


def invocation_result(actual: Invocation, expected: Invocation) -> PerInvocationResult:
    passed = trajectory_matches(
        get_all_tool_calls(actual.intermediate_data),
        get_all_tool_calls(expected.intermediate_data),
    )
    return PerInvocationResult(
        actual_invocation=actual,
        expected_invocation=expected,
        score=1.0 if passed else 0.0,
        eval_status=status_for(passed),
    )


def trajectory_subset_args(
    eval_metric: EvalMetric,
    actual_invocations: list[Invocation],
    expected_invocations: list[Invocation] | None,
    conversation_scenario: ConversationScenario | None = None,
) -> EvaluationResult:
    if expected_invocations is None:
        raise ValueError(f"{eval_metric.metric_name} needs expected invocations")
    results = [
        invocation_result(actual, expected)
        for actual, expected in zip(
            actual_invocations, expected_invocations, strict=True
        )
    ]
    passed = bool(results) and all(
        result.eval_status == EvalStatus.PASSED for result in results
    )
    score = sum(result.score or 0.0 for result in results) / max(len(results), 1)
    return EvaluationResult(
        overall_score=score,
        overall_eval_status=status_for(passed),
        per_invocation_results=results,
    )
