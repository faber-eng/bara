import facts from "@fixtures/cell_facts.json";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { callsTo, stubApi } from "../../test-utils";
import { CellDetail } from "./CellDetail";
import { DetailSheet } from "./DetailSheet";

vi.mock("../../lib/auth", () => ({ getIdToken: vi.fn().mockResolvedValue("token-1") }));

const SEND = "POST /api/ops/cells/riau-1/send";
const FACTS = "GET /api/cells/riau-1";
const CASES = "GET /api/cases?region=riau&limit=200";

function caseSummary() {
  return [
    {
      case: {
        id: "case-1",
        type: "dam_risk",
        region: "riau",
        cell_id: "riau-1",
        dam_id: null,
        event_id: null,
        status: "open",
        risk: { drying_score: 80, p_reignite: null },
        opened_at: "2026-10-01T00:00:00Z",
        closed_by: null,
        closed_at: null,
        history_flags: { smoke_seen: false },
        example: false,
      },
      next_deadline_at: null,
      task_status: null,
    },
  ];
}

function renderDetail(region: string, week?: string) {
  const queryClient = new QueryClient();
  render(
    <QueryClientProvider client={queryClient}>
      <DetailSheet closeLabel="Close" onClose={() => {}}>
        <CellDetail
          cellId="riau-1"
          region={region}
          week={week}
          onOpen={() => {}}
          onZoom={() => {}}
        />
      </DetailSheet>
    </QueryClientProvider>,
  );
  return queryClient;
}

function sendButton() {
  return screen.findByRole("button", { name: "Send someone" });
}

describe("CellDetail send someone", () => {
  beforeEach(() => {
    vi.stubEnv("VITE_SOURCE_CASES", "live");
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
  });

  it("is the first action and Zoom to area is secondary", async () => {
    stubApi({ [FACTS]: () => Response.json(facts), [CASES]: () => Response.json([]) });
    renderDetail("riau");

    const send = await sendButton();
    const zoom = screen.getByRole("button", { name: "Zoom to area" });
    expect(send.compareDocumentPosition(zoom) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(send).toHaveClass("btn-primary");
    expect(zoom).toHaveClass("btn-secondary");
  });

  it("is hidden for a region without the people flow", () => {
    stubApi({ [FACTS]: () => Response.json(facts) });
    renderDetail("congo_cuvette");

    expect(screen.queryByRole("button", { name: "Send someone" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Zoom to area" })).toHaveClass("btn-primary");
  });

  it("is hidden when the cell has an open case", async () => {
    stubApi({ [FACTS]: () => Response.json(facts), [CASES]: () => Response.json(caseSummary()) });
    renderDetail("riau");

    expect(await screen.findByRole("button", { name: "Open its case" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Send someone" })).not.toBeInTheDocument();
  });

  it("offers no button for a past week and says why", async () => {
    stubApi({ [FACTS]: () => Response.json(facts), [CASES]: () => Response.json([]) });
    renderDetail("riau", "2026-W41");

    expect(await screen.findByText("Send someone works on this week's ranking.")).toBeVisible();
    expect(screen.queryByRole("button", { name: "Send someone" })).not.toBeInTheDocument();
  });

  it("says the area is not in this week's ranking on 404", async () => {
    stubApi({
      [FACTS]: () => Response.json(facts),
      [CASES]: () => Response.json([]),
      [SEND]: () => Response.json({ detail: "unknown_cell" }, { status: 404 }),
    });
    renderDetail("riau");

    fireEvent.click(await sendButton());

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "This area is not in this week's ranking.",
    );
  });

  it("disables the button and says Sending while the request runs", async () => {
    stubApi({
      [FACTS]: () => Response.json(facts),
      [CASES]: () => Response.json([]),
      [SEND]: () => new Promise<Response>(() => {}) as never,
    });
    renderDetail("riau");

    fireEvent.click(await sendButton());

    const pending = await screen.findByRole("button", { name: "Sending…" });
    expect(pending).toBeDisabled();
  });

  it("replaces the button with a status line on 202 and refreshes the cases", async () => {
    const fetchMock = stubApi({
      [FACTS]: () => Response.json(facts),
      [CASES]: () => Response.json([]),
      [SEND]: () => Response.json({ cell_id: "riau-1", message_id: "m1" }, { status: 202 }),
    });
    renderDetail("riau");
    const before = callsTo(fetchMock, CASES).length;

    fireEvent.click(await sendButton());

    const status = await screen.findByText(
      "Bara is picking the nearest free person. The case shows in Cases in about 30 seconds.",
    );
    expect(status).toHaveAttribute("role", "status");
    expect(screen.queryByRole("button", { name: "Send someone" })).not.toBeInTheDocument();
    await waitFor(() => expect(callsTo(fetchMock, CASES).length).toBeGreaterThan(before));
  });

  it("says the area already has an open case on 409 case_open", async () => {
    stubApi({
      [FACTS]: () => Response.json(facts),
      [CASES]: () => Response.json([]),
      [SEND]: () => Response.json({ detail: "case_open" }, { status: 409 }),
    });
    renderDetail("riau");

    fireEvent.click(await sendButton());

    const status = await screen.findByText("This area already has an open case.");
    expect(status).toHaveAttribute("role", "status");
  });

  it("shows the server text in an alert on 429 and lets the user retry", async () => {
    stubApi({
      [FACTS]: () => Response.json(facts),
      [CASES]: () => Response.json([]),
      [SEND]: () => Response.json({ detail: "Too many sends. Wait a minute." }, { status: 429 }),
    });
    renderDetail("riau");

    fireEvent.click(await sendButton());

    expect(await screen.findByRole("alert")).toHaveTextContent("Too many sends. Wait a minute.");
    expect(screen.getByRole("button", { name: "Send someone" })).toBeEnabled();
  });

  it("shows a generic alert on other errors", async () => {
    stubApi({
      [FACTS]: () => Response.json(facts),
      [CASES]: () => Response.json([]),
      [SEND]: () => Response.json({ detail: "publish_failed" }, { status: 502 }),
    });
    renderDetail("riau");

    fireEvent.click(await sendButton());

    expect(await screen.findByRole("alert")).toHaveTextContent("Could not send. Try again.");
  });
});
