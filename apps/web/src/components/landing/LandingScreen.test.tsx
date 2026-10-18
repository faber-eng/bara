import { fireEvent, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { setCopyLanguage } from "../../lib/copy/language";
import { TOUR_STEPS } from "../../lib/tour/steps";
import { finishTour, goToStep, skipTour } from "../../lib/tour/store";
import { renderApp, stubApi } from "../../test-utils";

const SECTION_TITLES = [
  "Wet peat is safe. Dry peat is fuel.",
  "Before the dry season, and after a fire looks out.",
  "Five steps, from a satellite signal to a person with a task.",
  "What we measured, and where it falls short.",
  "Tested on data. Not yet in the field.",
];

function internalHrefs(): string[] {
  const hrefs = Array.from(document.querySelectorAll("main a")).map((link) =>
    link.getAttribute("href"),
  );
  return hrefs.filter((href): href is string => href?.startsWith("/") ?? false);
}

describe("landing pamphlet", () => {
  beforeEach(() => {
    localStorage.clear();
    finishTour();
    setCopyLanguage("en");
    return () => vi.unstubAllGlobals();
  });

  it("renders the hero and every section in order", async () => {
    stubApi({});
    renderApp("/");

    expect(
      await screen.findByRole("heading", {
        level: 1,
        name: "Bara finds drying peat and sends a person to check it before it burns.",
      }),
    ).toBeInTheDocument();
    const titles = screen.getAllByRole("heading", { level: 2 }).map((h) => h.textContent);
    expect(titles).toEqual(SECTION_TITLES);
    expect(
      screen.getByText(/Rizqy EP, Rama Dhaniansyah, Rafizhafran Halmi and Ramel Akil Pratama/),
    ).toBeInTheDocument();
  });

  it("draws the working and the broken dam", async () => {
    stubApi({});
    renderApp("/");

    expect(
      await screen.findByRole("img", { name: "Dam works: water stays high, peat stays wet" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("img", { name: "Dam broken: water drains, top peat dries" }),
    ).toBeInTheDocument();
  });

  it("shows which steps the AI does and which people do", async () => {
    stubApi({});
    renderApp("/");

    const loop = await screen.findByRole("list", { name: "The five steps" });
    const steps = within(loop).getAllByRole("listitem");
    expect(steps).toHaveLength(5);
    for (const step of steps) {
      expect(within(step).getByText("AI does")).toBeInTheDocument();
      expect(within(step).getByText("People do")).toBeInTheDocument();
    }
  });

  it("keeps the tour buttons and their actions", async () => {
    stubApi({});
    const { router } = renderApp("/");

    expect(await screen.findByRole("link", { name: "Explore freely" })).toHaveAttribute(
      "href",
      "/public",
    );
    fireEvent.click(screen.getByRole("button", { name: "Start the guided tour" }));

    expect(await screen.findByText(`Step 1 of ${TOUR_STEPS.length}`)).toBeInTheDocument();
    expect(router.history.location.pathname).toBe("/public");
  });

  it("keeps the resume button label", async () => {
    stubApi({});
    renderApp("/");
    goToStep(2);
    skipTour();

    expect(
      await screen.findByRole("button", { name: `Resume at step 3 of ${TOUR_STEPS.length}` }),
    ).toBeInTheDocument();
  });

  it("states the eval numbers with their sample sizes", async () => {
    stubApi({});
    renderApp("/");

    const proof = await screen.findByRole("region", { name: SECTION_TITLES[3] });
    expect(within(proof).getByText("2.68x")).toBeInTheDocument();
    expect(within(proof).getByText("2.36x")).toBeInTheDocument();
    expect(within(proof).getByText("3,573")).toBeInTheDocument();
    expect(within(proof).getByText("82.5%")).toBeInTheDocument();
    expect(within(proof).getByText("n = 40 photos")).toBeInTheDocument();
    expect(within(proof).getByText("9 of 9")).toBeInTheDocument();
    expect(within(proof).getByRole("link", { name: "How well it works" })).toHaveAttribute(
      "href",
      "/public",
    );
  });

  it("says the re-ignition model does not beat the simple rule", async () => {
    stubApi({});
    renderApp("/");

    expect(
      await screen.findByText(
        "The re-ignition model does not beat a simple rule yet. On the test fires it scored AUC 0.662; ranking by days of detection scored 0.708. Only 13 of 118 fires came back, so the gap is inside the noise. We show both.",
      ),
    ).toBeInTheDocument();
  });

  it("says where it runs and that there is no field programme", async () => {
    stubApi({});
    renderApp("/");

    expect(await screen.findByText(/We do not run a field programme there\./)).toBeInTheDocument();
    expect(screen.getByText("Drying ranking and map only.")).toBeInTheDocument();
    expect(screen.getByText(/CC BY-NC-SA 4\.0/)).toBeInTheDocument();
  });

  it("links only to routes that exist", async () => {
    stubApi({});
    const { router } = renderApp("/");
    await screen.findByRole("navigation", { name: "Open a screen" });

    const hrefs = internalHrefs();
    expect(hrefs.length).toBeGreaterThan(0);
    for (const href of hrefs) {
      expect(router.routesByPath).toHaveProperty([href]);
    }
  });

  it("makes no API call of its own", async () => {
    const fetchMock = stubApi({});
    renderApp("/");
    await screen.findByRole("heading", { level: 1 });
    await screen.findByText("API ok");

    const paths = fetchMock.mock.calls.map(([path]) => path);
    expect(paths.filter((path) => path !== "/api/health")).toEqual([]);
  });

  it("renders in Indonesian", async () => {
    setCopyLanguage("id");
    stubApi({});
    renderApp("/");

    expect(
      await screen.findByRole("heading", {
        level: 1,
        name: "Bara menemukan gambut yang mulai kering dan mengirim orang untuk mengeceknya sebelum terbakar.",
      }),
    ).toBeInTheDocument();
    expect(screen.getByText("Hanya peringkat kering dan peta.")).toBeInTheDocument();
    expect(screen.getByText(/AUC model 0,662/)).toBeInTheDocument();
  });

  it("switches language from the toggle", async () => {
    stubApi({});
    renderApp("/");

    fireEvent.click(await screen.findByRole("button", { name: "ID" }));

    expect(
      await screen.findByRole("heading", {
        level: 2,
        name: "Gambut basah aman. Gambut kering jadi bahan bakar.",
      }),
    ).toBeInTheDocument();
  });
});
