import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { callsTo, stubApi } from "../../test-utils";
import { ReviewQueueTab } from "./ReviewQueueTab";

vi.mock("../../lib/auth", () => ({ getIdToken: vi.fn().mockResolvedValue("token-1") }));

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

function renderTab(region = "riau") {
  const onOpen = vi.fn();
  const onShowCases = vi.fn();
  render(
    <QueryClientProvider client={new QueryClient()}>
      <ReviewQueueTab region={region} onOpen={onOpen} onShowCases={onShowCases} />
    </QueryClientProvider>,
  );
  return { onOpen, onShowCases };
}

function liveCases(extra: Parameters<typeof stubApi>[0] = {}) {
  vi.stubEnv("VITE_SOURCE_CASES", "live");
  vi.stubEnv("VITE_SOURCE_CASEDETAIL", "live");
  return stubApi({ "GET /api/cases?region=riau&limit=200": () => Response.json(QUEUE), ...extra });
}

describe("ReviewQueueTab", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("lists only the cases in human review, in plain words", async () => {
    liveCases();
    renderTab();

    const row = await screen.findByRole("button", { name: /riau-0277/ });
    expect(row).toHaveTextContent("Dam risk");
    expect(row).not.toHaveTextContent("dam_risk");
    expect(screen.queryByText(/riau-0610/)).not.toBeInTheDocument();
  });

  it("explains the empty queue and offers the open cases", async () => {
    liveCases({ "GET /api/cases?region=riau&limit=200": () => Response.json([QUEUE[1]]) });
    const { onShowCases } = renderTab();

    expect(await screen.findByRole("heading", { name: "Nothing to review" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Show open cases" }));

    expect(onShowCases).toHaveBeenCalled();
  });

  it("opens the review dialog from the row", async () => {
    liveCases();
    const { onOpen } = renderTab();

    fireEvent.click(await screen.findByRole("button", { name: /riau-0277/ }));

    expect(onOpen).toHaveBeenCalledWith("case-human");
  });

  it("shows the Congo note and asks for no cases", () => {
    const fetchMock = liveCases();
    renderTab("congo_cuvette");

    expect(screen.getByText(/Congo shows rankings and map layers only/)).toBeInTheDocument();
    expect(callsTo(fetchMock, "GET /api/cases?region=congo_cuvette&limit=200")).toHaveLength(0);
  });
});
