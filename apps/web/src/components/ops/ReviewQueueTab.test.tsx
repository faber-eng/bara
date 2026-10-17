import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { callsTo, initOf, stubApi } from "../../test-utils";
import { ReviewQueueTab } from "./ReviewQueueTab";

vi.mock("../../lib/auth", () => ({ getIdToken: vi.fn().mockResolvedValue("token-1") }));

const REVIEW_KEY = "POST /api/cases/case-human/review";

function summary(id: string, cell: string, status: string) {
  return {
    case: {
      id,
      type: "dam_risk",
      region: "riau",
      cell_id: cell,
      dam_id: null,
      event_id: null,
      status,
      risk: { drying_score: 70, p_reignite: null },
      opened_at: "2026-10-01T00:00:00Z",
      closed_by: null,
      closed_at: null,
      history_flags: { smoke_seen: false },
      example: false,
    },
    next_deadline_at: null,
    task_status: null,
  };
}

const QUEUE = [
  summary("case-human", "riau-0277", "human_review"),
  summary("case-open", "riau-0610", "open"),
];

function renderTab(region = "riau", onCaseSelect = vi.fn()) {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <ReviewQueueTab region={region} onCaseSelect={onCaseSelect} />
    </QueryClientProvider>,
  );
  return onCaseSelect;
}

function liveCases(extra: Parameters<typeof stubApi>[0] = {}) {
  vi.stubEnv("VITE_SOURCE_CASES", "live");
  vi.stubEnv("VITE_SOURCE_CASEDETAIL", "live");
  return stubApi({ "GET /api/cases?region=riau&limit=200": () => Response.json(QUEUE), ...extra });
}

async function openForm() {
  fireEvent.click(await screen.findByRole("button", { name: "Review" }));
  return screen.findByRole("form", { name: "Review riau-0277" });
}

describe("ReviewQueueTab", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("lists only the cases in human review", async () => {
    liveCases();
    renderTab();

    expect(await screen.findByText(/riau-0277/)).toBeInTheDocument();
    expect(screen.queryByText(/riau-0610/)).not.toBeInTheDocument();
  });

  it("says nothing waits when no case is in human review", async () => {
    liveCases({ "GET /api/cases?region=riau&limit=200": () => Response.json([QUEUE[1]]) });
    renderTab();

    expect(await screen.findByText("Nothing waits for human review.")).toBeInTheDocument();
  });

  it("opens the case from the row", async () => {
    liveCases();
    const onCaseSelect = renderTab();

    fireEvent.click(await screen.findByRole("button", { name: "Open case" }));

    expect(onCaseSelect).toHaveBeenCalledWith("case-human");
  });

  it("keeps save disabled until the note has text", async () => {
    liveCases();
    renderTab();
    await openForm();

    const save = screen.getByRole("button", { name: "Save review" });
    expect(save).toBeDisabled();
    fireEvent.change(screen.getByLabelText(/Note/), { target: { value: "   " } });
    expect(save).toBeDisabled();
    fireEvent.change(screen.getByLabelText(/Note/), { target: { value: "checked photos" } });
    expect(save).toBeEnabled();
  });

  it.each([
    ["Assign", "assign"],
    ["Escalate", "escalate"],
    ["Close", "close"],
  ])("posts the %s action with the note", async (label, action) => {
    const fetchMock = liveCases({ [REVIEW_KEY]: () => Response.json(QUEUE[0]?.case) });
    renderTab();
    await openForm();

    fireEvent.click(screen.getByRole("radio", { name: new RegExp(label) }));
    fireEvent.change(screen.getByLabelText(/Note/), { target: { value: " site checked " } });
    fireEvent.click(screen.getByRole("button", { name: "Save review" }));

    await waitFor(() => expect(callsTo(fetchMock, REVIEW_KEY)).toHaveLength(1));
    const call = callsTo(fetchMock, REVIEW_KEY)[0];
    expect(JSON.parse(initOf(call).body as string)).toEqual({ action, note: "site checked" });
  });

  it("refreshes the queue after a save and closes the form", async () => {
    let status = "human_review";
    const fetchMock = liveCases({
      "GET /api/cases?region=riau&limit=200": () =>
        Response.json([summary("case-human", "riau-0277", status)]),
      [REVIEW_KEY]: () => {
        status = "closed";
        return Response.json(summary("case-human", "riau-0277", status).case);
      },
    });
    renderTab();
    await openForm();
    fireEvent.change(screen.getByLabelText(/Note/), { target: { value: "done" } });

    fireEvent.click(screen.getByRole("button", { name: "Save review" }));

    expect(await screen.findByText("Nothing waits for human review.")).toBeInTheDocument();
    expect(callsTo(fetchMock, "GET /api/cases?region=riau&limit=200")).toHaveLength(2);
  });

  it("says when another reviewer got there first", async () => {
    liveCases({ [REVIEW_KEY]: () => Response.json({ detail: "not_in_review" }, { status: 409 }) });
    renderTab();
    await openForm();
    fireEvent.change(screen.getByLabelText(/Note/), { target: { value: "done" } });

    fireEvent.click(screen.getByRole("button", { name: "Save review" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("no longer in human review");
  });

  it("shows the Congo note and asks for no cases", () => {
    const fetchMock = liveCases();
    renderTab("congo_cuvette");

    expect(screen.getByText(/Congo shows rankings and map layers only/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Review" })).not.toBeInTheDocument();
    expect(callsTo(fetchMock, "GET /api/cases?region=congo_cuvette&limit=200")).toHaveLength(0);
  });
});
