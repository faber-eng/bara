import detail from "@fixtures/case_detail.json";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { resetClock } from "../../lib/api/clock";
import { clearFixtureClosures } from "../../lib/api/fixtureClosures";
import { callsTo, stubApi } from "../../test-utils";
import { CaseDrawer } from "./CaseDrawer";

vi.mock("../../lib/auth", () => ({ getIdToken: vi.fn().mockResolvedValue("token-1") }));

function renderDrawer(caseId: string, onBack = vi.fn()) {
  const queryClient = new QueryClient();
  render(
    <QueryClientProvider client={queryClient}>
      <CaseDrawer caseId={caseId} onBack={onBack} />
    </QueryClientProvider>,
  );
  return { onBack, queryClient };
}

describe("CaseDrawer", () => {
  beforeEach(async () => {
    clearFixtureClosures();
    await resetClock();
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("shows the timeline, the evidence verdicts and the agent runs", async () => {
    renderDrawer("case-0001");

    expect(await screen.findByRole("heading", { name: /riau-0412/ })).toBeInTheDocument();
    const timeline = screen.getByRole("region", { name: "Timeline" });
    expect(within(timeline).getAllByRole("listitem")).toHaveLength(3);
    const evidence = screen.getByRole("region", { name: "Evidence" });
    expect(within(evidence).getAllByText("Gemini")).toHaveLength(2);
    expect(within(evidence).getByText("Confidence 90%")).toBeInTheDocument();
    expect(
      within(evidence).getByText(
        "gap through the dam wall; water flows through the gap; canal level below the crest",
      ),
    ).toBeInTheDocument();
    expect(
      within(evidence).getByText("The dam is broken on the left side, the canal water has dropped"),
    ).toBeInTheDocument();
  });

  it("labels example data", async () => {
    renderDrawer("case-0001");

    expect(await screen.findByText("Example data")).toBeInTheDocument();
  });

  it("opens the agent run from Why?", async () => {
    renderDrawer("case-0001");
    const runs = await screen.findByRole("region", { name: "Agent runs" });
    const run = runs.querySelector("details");
    expect(run).not.toHaveAttribute("open");

    fireEvent.click(screen.getAllByRole("button", { name: "Why?" })[0] as HTMLElement);

    await waitFor(() => expect(run).toHaveAttribute("open"));
    expect(within(runs).getByText("find_people")).toBeInTheDocument();
    expect(within(runs).getByText("2310 ms")).toBeInTheDocument();
    expect(within(runs).getByText(/gemini-3.1-pro-preview · prompt agent-v1/)).toBeInTheDocument();
    expect(
      within(runs).getByText(
        'case_id="case-0001", assignee_id="vol-ari", task_type="dam_check", deadline_hours=72',
      ),
    ).toBeInTheDocument();
  });

  it("offers no Close for an assigned case", async () => {
    renderDrawer("case-0001");

    await screen.findByRole("heading", { name: /riau-0412/ });
    expect(screen.queryByRole("button", { name: "Close case" })).not.toBeInTheDocument();
  });

  it("closes a resolved case and shows it closed", async () => {
    renderDrawer("case-0005");

    fireEvent.click(await screen.findByRole("button", { name: "Close case" }));

    expect(await screen.findByText("Closed")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Close case" })).not.toBeInTheDocument();
  });

  it("posts to the close route when live and refreshes the case lists", async () => {
    vi.stubEnv("VITE_SOURCE_CASEDETAIL", "live");
    let status = "resolved_pending_human";
    const fetchMock = stubApi({
      "GET /api/cases/case-0005": () =>
        Response.json({ ...detail, case: { ...detail.case, id: "case-0005", status } }),
      "POST /api/cases/case-0005/close": () => {
        status = "closed";
        return Response.json({});
      },
    });
    const { queryClient } = renderDrawer("case-0005");
    const invalidate = vi.spyOn(queryClient, "invalidateQueries");

    fireEvent.click(await screen.findByRole("button", { name: "Close case" }));

    await waitFor(() =>
      expect(callsTo(fetchMock, "POST /api/cases/case-0005/close")).toHaveLength(1),
    );
    await waitFor(() => expect(invalidate).toHaveBeenCalledWith({ queryKey: ["cases"] }));
    expect(await screen.findByText("Closed")).toBeInTheDocument();
  });

  it("keeps the button and says so when close fails", async () => {
    vi.stubEnv("VITE_SOURCE_CASEDETAIL", "live");
    const fetchMock = stubApi({
      "GET /api/cases/case-0005": () =>
        Response.json({ ...detail, case: { ...detail.case, status: "human_review" } }),
      "POST /api/cases/case-0005/close": () => new Response("no", { status: 409 }),
    });
    renderDrawer("case-0005");

    fireEvent.click(await screen.findByRole("button", { name: "Close case" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Could not close the case");
    expect(callsTo(fetchMock, "GET /api/cases/case-0005").length).toBeGreaterThan(1);
    expect(screen.getByRole("button", { name: "Close case" })).toBeEnabled();
  });

  it("shows an error with retry when the detail fails", async () => {
    vi.stubEnv("VITE_SOURCE_CASEDETAIL", "live");
    stubApi({ "GET /api/cases/case-0005": () => new Response("x", { status: 500 }) });
    renderDrawer("case-0005");

    expect(await screen.findByRole("alert")).toHaveTextContent("Could not load the case");
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });

  it("shows empty sections for a case with no evidence or runs", async () => {
    renderDrawer("case-0002");

    expect(await screen.findByText("No evidence yet.")).toBeInTheDocument();
    expect(screen.getByText("The agent has not run on this case.")).toBeInTheDocument();
    expect(screen.getByText("No events yet.")).toBeInTheDocument();
  });

  it("goes back to the list", async () => {
    const { onBack } = renderDrawer("case-0001");

    fireEvent.click(await screen.findByRole("button", { name: "Back to list" }));

    expect(onBack).toHaveBeenCalled();
  });
});
