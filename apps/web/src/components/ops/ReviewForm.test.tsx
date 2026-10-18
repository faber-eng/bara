import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { callsTo, initOf, stubApi } from "../../test-utils";
import { ReviewForm } from "./ReviewForm";

vi.mock("../../lib/auth", () => ({ getIdToken: vi.fn().mockResolvedValue("token-1") }));

const REVIEW_KEY = "POST /api/cases/case-human/review";
const RECORD = { id: "case-human", cell_id: "riau-0277" };
const REVIEWED = {
  id: "case-human",
  type: "dam_risk",
  region: "riau",
  cell_id: "riau-0277",
  dam_id: null,
  event_id: null,
  status: "assigned",
  risk: { drying_score: 70, p_reignite: null },
  opened_at: "2026-10-01T00:00:00Z",
  closed_by: null,
  closed_at: null,
  history_flags: { smoke_seen: false },
  example: false,
};

function renderForm(handlers: Parameters<typeof stubApi>[0] = {}) {
  vi.stubEnv("VITE_SOURCE_CASES", "live");
  vi.stubEnv("VITE_SOURCE_CASEDETAIL", "live");
  const fetchMock = stubApi(handlers);
  const queryClient = new QueryClient();
  const invalidate = vi.spyOn(queryClient, "invalidateQueries");
  const onDone = vi.fn();
  render(
    <QueryClientProvider client={queryClient}>
      <ReviewForm record={RECORD} onDone={onDone} />
    </QueryClientProvider>,
  );
  return { fetchMock, invalidate, onDone };
}

function writeNote(value: string) {
  fireEvent.change(screen.getByLabelText(/Note/), { target: { value } });
}

describe("ReviewForm", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("keeps save disabled until the note has text", () => {
    renderForm();

    const save = screen.getByRole("button", { name: "Save review" });
    expect(save).toBeDisabled();
    writeNote("   ");
    expect(save).toBeDisabled();
    writeNote("checked photos");
    expect(save).toBeEnabled();
  });

  it.each([
    ["Assign", "assign"],
    ["Escalate", "escalate"],
    ["Close", "close"],
  ])("posts the %s action with the note", async (label, action) => {
    const { fetchMock } = renderForm({ [REVIEW_KEY]: () => Response.json(REVIEWED) });

    fireEvent.click(screen.getByRole("radio", { name: new RegExp(label) }));
    writeNote(" site checked ");
    fireEvent.click(screen.getByRole("button", { name: "Save review" }));

    await waitFor(() => expect(callsTo(fetchMock, REVIEW_KEY)).toHaveLength(1));
    const call = callsTo(fetchMock, REVIEW_KEY)[0];
    expect(JSON.parse(initOf(call).body as string)).toEqual({ action, note: "site checked" });
  });

  it("refreshes the case lists and reports done after a save", async () => {
    const { invalidate, onDone } = renderForm({ [REVIEW_KEY]: () => Response.json(REVIEWED) });
    writeNote("done");

    fireEvent.click(screen.getByRole("button", { name: "Save review" }));

    await waitFor(() => expect(onDone).toHaveBeenCalled());
    await waitFor(() => expect(invalidate).toHaveBeenCalledWith({ queryKey: ["cases"] }));
  });

  it("says when another reviewer got there first", async () => {
    renderForm({
      [REVIEW_KEY]: () => Response.json({ detail: "not_in_review" }, { status: 409 }),
    });
    writeNote("done");

    fireEvent.click(screen.getByRole("button", { name: "Save review" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("no longer in human review");
  });
});
