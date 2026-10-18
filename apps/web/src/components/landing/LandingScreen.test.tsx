import { fireEvent, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { setCopyLanguage } from "../../lib/copy/language";
import { TOUR_STEPS } from "../../lib/tour/steps";
import { finishTour, goToStep, skipTour } from "../../lib/tour/store";
import { renderApp, stubApi } from "../../test-utils";

const SECTION_TITLES = ["Why dry peat burns", "What Bara does", "Why we built it", "See it work"];

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

  it("tells the two moments once", async () => {
    stubApi({});
    renderApp("/");

    const solution = await screen.findByRole("region", { name: SECTION_TITLES[1] });
    expect(
      within(solution)
        .getAllByRole("heading", { level: 3 })
        .map((h) => h.textContent),
    ).toEqual(["Before the dry season", "After a fire looks out"]);
  });

  it("has no loop, proof or where-it-runs section", async () => {
    stubApi({});
    renderApp("/");
    await screen.findByRole("heading", { level: 1 });

    expect(screen.queryByRole("list", { name: "The five steps" })).not.toBeInTheDocument();
    expect(screen.queryByText("2.68x")).not.toBeInTheDocument();
    expect(screen.queryByText(/field programme/)).not.toBeInTheDocument();
  });

  it("closes with a tour button and a link to the public page", async () => {
    stubApi({});
    const { router } = renderApp("/");

    const closing = await screen.findByRole("region", { name: SECTION_TITLES[3] });
    expect(within(closing).getByRole("link", { name: "Open the public page" })).toHaveAttribute(
      "href",
      "/public",
    );
    fireEvent.click(within(closing).getByRole("button", { name: "Take the tour" }));

    expect(await screen.findByText(`Step 1 of ${TOUR_STEPS.length}`)).toBeInTheDocument();
    expect(router.history.location.pathname).toBe("/public");
  });

  it("says the work is tested on data, not yet in the field", async () => {
    stubApi({});
    renderApp("/");

    const why = await screen.findByRole("region", { name: SECTION_TITLES[2] });
    expect(within(why).getByText(/not yet in the field/)).toBeInTheDocument();
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

  it("links only to routes that exist", async () => {
    stubApi({});
    const { router } = renderApp("/");
    await screen.findByRole("heading", { level: 1 });

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
    expect(
      screen.getByRole("heading", { level: 2, name: "Kenapa kami membuatnya" }),
    ).toBeInTheDocument();
  });

  it("switches language from the toggle", async () => {
    stubApi({});
    renderApp("/");

    fireEvent.click(await screen.findByRole("button", { name: "ID" }));

    expect(
      await screen.findByRole("heading", {
        level: 2,
        name: "Kenapa gambut kering mudah terbakar",
      }),
    ).toBeInTheDocument();
  });
});
