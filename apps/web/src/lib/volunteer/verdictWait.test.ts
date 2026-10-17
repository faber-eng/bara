import { describe, expect, it, vi } from "vitest";
import type { Evidence } from "../contracts";
import { waitForVerdict } from "./verdictWait";

function evidence(id: string, judged: boolean): Evidence {
  return {
    id,
    task_id: "t1",
    case_id: "c1",
    kind: "photo",
    gcs_uri: "gs://b/x",
    sha256: "0".repeat(64),
    point: null,
    captured_at: null,
    verdict: judged
      ? {
          subject: "canal_dam",
          dam_state: "broken",
          smoke: "none",
          hot_ground_signs: "none",
          open_flame: "no",
          transcript: null,
          transcript_en: null,
          reasons: [],
          confidence: 0.9,
          needs_human: false,
        }
      : null,
    location_ok: true,
    uploaded_by: "vol-ari",
    sample: false,
  };
}

describe("waitForVerdict", () => {
  it("returns the evidence once its verdict arrives", async () => {
    const readEvidence = vi
      .fn()
      .mockResolvedValueOnce([evidence("e1", false)])
      .mockResolvedValueOnce([evidence("e1", true)]);
    const wait = vi.fn().mockResolvedValue(undefined);

    const found = await waitForVerdict({ evidenceId: "e1", readEvidence, wait });

    expect(found?.verdict?.dam_state).toBe("broken");
    expect(readEvidence).toHaveBeenCalledTimes(2);
    expect(wait).toHaveBeenCalledTimes(1);
  });

  it("ignores other evidence rows", async () => {
    const readEvidence = vi.fn().mockResolvedValue([evidence("other", true)]);
    const wait = vi.fn().mockResolvedValue(undefined);

    const found = await waitForVerdict({ evidenceId: "e1", readEvidence, wait, attempts: 3 });

    expect(found).toBeNull();
    expect(readEvidence).toHaveBeenCalledTimes(3);
  });

  it("gives up with null after the attempts run out", async () => {
    const readEvidence = vi.fn().mockResolvedValue([evidence("e1", false)]);

    const found = await waitForVerdict({
      evidenceId: "e1",
      readEvidence,
      wait: vi.fn().mockResolvedValue(undefined),
      attempts: 2,
    });

    expect(found).toBeNull();
  });

  it("lets a read failure through", async () => {
    const readEvidence = vi.fn().mockRejectedValue(new Error("offline"));

    await expect(waitForVerdict({ evidenceId: "e1", readEvidence, wait: vi.fn() })).rejects.toThrow(
      "offline",
    );
  });

  it("stops reading once cancelled", async () => {
    const readEvidence = vi.fn().mockResolvedValue([]);

    const found = await waitForVerdict({
      evidenceId: "e1",
      readEvidence,
      wait: vi.fn().mockResolvedValue(undefined),
      isCancelled: () => true,
    });

    expect(found).toBeNull();
    expect(readEvidence).not.toHaveBeenCalled();
  });
});
