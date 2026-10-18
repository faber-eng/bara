import { describe, expect, it } from "vitest";
import { photoDamState } from "./proof";

const RUN = { runAt: "2026-10-17T21:12:15Z", model: "m" };

describe("photoDamState", () => {
  it("reads the dam state accuracy of the photo set", () => {
    const evidence = {
      ...RUN,
      sets: [
        {
          kind: "audio",
          n: 10,
          failed: 0,
          fields: [{ field: "dam_state", correct: 10, n: 10, accuracy: 1 }],
        },
        {
          kind: "photo",
          n: 40,
          failed: 0,
          fields: [{ field: "dam_state", correct: 33, n: 40, accuracy: 0.825 }],
        },
      ],
    };

    expect(photoDamState(evidence)).toEqual({
      field: "dam_state",
      correct: 33,
      n: 40,
      accuracy: 0.825,
    });
  });

  it("is null when evidence was not run or has no photo set", () => {
    expect(photoDamState(null)).toBeNull();
    expect(photoDamState({ ...RUN, sets: [] })).toBeNull();
  });
});
