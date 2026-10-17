import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { TimelineEntry } from "../../lib/contracts";
import { CaseTimeline } from "./CaseTimeline";

const OPENED: TimelineEntry = {
  at: "2026-10-01T10:00:00Z",
  text: "Case opened: dam_risk at riau-1",
};
const ESCALATED: TimelineEntry = { at: "2026-10-05T10:00:00Z", text: "Escalated to brigade b-1" };

describe("CaseTimeline", () => {
  it("labels an escalation the code made", () => {
    render(<CaseTimeline entries={[OPENED, ESCALATED]} ruleMade={new Set([ESCALATED])} />);

    expect(screen.getAllByText("Escalated by overdue rule")).toHaveLength(1);
  });

  it("adds no label when nothing is marked", () => {
    render(<CaseTimeline entries={[OPENED, ESCALATED]} />);

    expect(screen.queryByText("Escalated by overdue rule")).not.toBeInTheDocument();
  });

  it("says when there are no events", () => {
    render(<CaseTimeline entries={[]} />);

    expect(screen.getByText("No events yet.")).toBeInTheDocument();
  });
});
