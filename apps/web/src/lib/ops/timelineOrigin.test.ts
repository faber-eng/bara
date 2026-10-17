import { describe, expect, it } from "vitest";
import type { AgentRun, Task, TimelineEntry } from "../contracts";
import { ruleEscalationEntries } from "./timelineOrigin";

const ESCALATED: TimelineEntry = { at: "2026-10-05T10:00:00Z", text: "Escalated to brigade b-1" };
const OPENED: TimelineEntry = {
  at: "2026-10-01T10:00:00Z",
  text: "Case opened: dam_risk at riau-1",
};
const NOTE: TimelineEntry = { at: "2026-10-05T09:00:00Z", text: "Review note: sending it up" };

function task(status: Task["status"]): Task {
  return { status } as Task;
}

function runCalling(...names: string[]): AgentRun {
  return { tool_calls: names.map((name) => ({ name })) } as AgentRun;
}

describe("ruleEscalationEntries", () => {
  it("marks an escalation after an overdue task with no agent escalate call and no review note", () => {
    const detail = { timeline: [OPENED, ESCALATED], agent_runs: [], tasks: [task("overdue")] };

    expect([...ruleEscalationEntries(detail)]).toEqual([ESCALATED]);
  });

  it("marks it when the agent only reassigned", () => {
    const detail = {
      timeline: [OPENED, ESCALATED],
      agent_runs: [runCalling("assign_task")],
      tasks: [task("overdue")],
    };

    expect(ruleEscalationEntries(detail).size).toBe(1);
  });

  it("leaves an escalation the agent made", () => {
    const detail = {
      timeline: [OPENED, ESCALATED],
      agent_runs: [runCalling("check_evidence", "escalate")],
      tasks: [task("overdue")],
    };

    expect(ruleEscalationEntries(detail).size).toBe(0);
  });

  it("leaves an escalation a person made in review", () => {
    const detail = {
      timeline: [OPENED, NOTE, ESCALATED],
      agent_runs: [],
      tasks: [task("overdue")],
    };

    expect(ruleEscalationEntries(detail).size).toBe(0);
  });

  it("leaves an escalation on a case with no overdue task", () => {
    const detail = { timeline: [OPENED, ESCALATED], agent_runs: [], tasks: [task("done")] };

    expect(ruleEscalationEntries(detail).size).toBe(0);
  });
});
