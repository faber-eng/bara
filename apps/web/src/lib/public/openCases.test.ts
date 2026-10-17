import { describe, expect, it } from "vitest";
import type { RecordLine } from "../contracts";
import { openCaseCells } from "./openCases";

function line(cell_id: string, kind: RecordLine["kind"], at: string): RecordLine {
  return { cell_id, kind, at, text: "x" };
}

describe("openCaseCells", () => {
  it("keeps the cells whose latest line is not a close", () => {
    const record = [
      line("riau-1", "opened", "2026-10-12T01:00:00Z"),
      line("riau-1", "closed", "2026-10-13T01:00:00Z"),
      line("riau-2", "opened", "2026-10-12T01:00:00Z"),
      line("riau-2", "escalated", "2026-10-14T01:00:00Z"),
    ];

    expect(openCaseCells(record)).toEqual(["riau-2"]);
  });

  it("is empty for an empty record", () => {
    expect(openCaseCells([])).toEqual([]);
  });
});
