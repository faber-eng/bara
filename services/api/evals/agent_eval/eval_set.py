import sys
from pathlib import Path

from google.adk.evaluation.eval_case import EvalCase, IntermediateData, Invocation
from google.adk.evaluation.eval_set import EvalSet
from google.genai import types

from evals.agent_eval.scenarios import Scenario, build_scenarios

EVALS_DIR = Path(__file__).resolve().parents[1]
EVAL_SET_PATH = EVALS_DIR / "agent.test.json"
EVAL_SET_ID = "bara_agent"


def expected_calls(scenario: Scenario) -> list[types.FunctionCall]:
    return [
        types.FunctionCall(name=call.name, args=call.args) for call in scenario.expected
    ]


def eval_case(scenario: Scenario) -> EvalCase:
    invocation = Invocation(
        invocation_id=scenario.id,
        user_content=types.Content(
            role="user", parts=[types.Part(text=scenario.run_input())]
        ),
        intermediate_data=IntermediateData(tool_uses=expected_calls(scenario)),
    )
    return EvalCase(eval_id=scenario.id, conversation=[invocation])


def build_eval_set() -> EvalSet:
    return EvalSet(
        eval_set_id=EVAL_SET_ID,
        name="Bara coordinator decisions",
        eval_cases=[eval_case(scenario) for scenario in build_scenarios()],
    )


def render_eval_set() -> str:
    return build_eval_set().model_dump_json(indent=2, exclude_none=True) + "\n"


def main() -> int:
    EVAL_SET_PATH.write_text(render_eval_set(), encoding="utf-8")
    sys.stdout.write(f"wrote {EVAL_SET_PATH}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
