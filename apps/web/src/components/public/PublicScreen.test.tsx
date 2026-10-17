import { screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { callsTo, headerOf, renderApp, stubApi } from "../../test-utils";

const getIdToken = vi.hoisted(() => vi.fn().mockResolvedValue("token-1"));
vi.mock("../../lib/auth", () => ({ getIdToken }));

const SUMMARY = {
  region: "riau",
  week: "2026-W42",
  high_risk_cells: 12,
  dams_broken: 3,
  cases_open: 4,
  cases_escalated: 1,
  cases_closed: 2,
  median_days_to_repair: null,
  tasks_on_time_pct: 80,
  data_as_of: { s1_pass_date: "2026-10-12", ranking_run_at: "2026-10-11T17:00:00Z" },
};

const CELLS = { region: "riau", week: "2026-W42", cells: [] };

const BULLETIN = {
  region: "riau",
  week: "2026-W42",
  text_id: "Minggu ini 12 petak berisiko tinggi.",
  text_en: "This week 12 cells are at high risk.",
  cited: [{ field: "high_risk_cells", value: 12 }],
  source: "gemini",
  model: "gemini-3.5-flash",
  prompt_version: "bulletin-v1",
  created_at: "2026-10-17T04:00:00Z",
};

const RECORD = [
  {
    at: "2026-10-17T03:00:00Z",
    cell_id: "riau-0412",
    kind: "opened",
    text: "Dam flagged at risk in riau-0412.",
  },
];

function handlers(bulletin: object = BULLETIN) {
  return {
    "GET /api/public/riau/summary": () => Response.json(SUMMARY),
    "GET /api/public/riau/cells?limit=200": () => Response.json(CELLS),
    "GET /api/public/riau/bulletin": () => Response.json(bulletin),
    "GET /api/public/riau/record?limit=50": () => Response.json(RECORD),
    "GET /api/public/riau/dams": () => Response.json([]),
  };
}

describe("PublicScreen", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    getIdToken.mockClear();
  });

  it("opens with no sign-in: no token is requested and no call carries credentials", async () => {
    const fetchMock = stubApi(handlers());

    renderApp("/public");

    expect(await screen.findByText("Petak berisiko tinggi")).toBeInTheDocument();
    await screen.findByText("Catatan respons", { exact: false });
    expect(getIdToken).not.toHaveBeenCalled();
    expect(callsTo(fetchMock, "GET /api/clock")).toHaveLength(0);
    for (const call of fetchMock.mock.calls) {
      expect(headerOf(call, "Authorization")).toBeNull();
    }
  });

  it("shows the stat strip with units, a zero-free median message and the data date", async () => {
    stubApi(handlers());

    renderApp("/public");

    const strip = await screen.findByText("Hari perbaikan");
    expect(strip).toBeInTheDocument();
    expect(screen.getByText("Belum ada perbaikan selesai minggu ini")).toBeInTheDocument();
    expect(screen.getByText("1 diteruskan ke pemadam")).toBeInTheDocument();
    const source = screen.getByText("Petak berisiko tinggi").closest(".stat");
    expect(source?.getAttribute("title")).toContain("high_risk_cells");
    expect(source?.getAttribute("title")).toContain("2026");
  });

  it("shows a Gemini bulletin in both languages with the chip and its cited fields", async () => {
    stubApi(handlers());

    renderApp("/public");

    expect(await screen.findByText("Buletin Gemini")).toBeInTheDocument();
    expect(screen.getByText("Minggu ini 12 petak berisiko tinggi.")).toBeInTheDocument();
    expect(screen.getByText("This week 12 cells are at high risk.")).toBeInTheDocument();
    const how = screen.getByText("Cara buletin ini ditulis").closest("details");
    expect(how).not.toBeNull();
    if (how === null) return;
    expect(within(how).getByText("gemini-3.5-flash")).toBeInTheDocument();
    expect(within(how).getByText("bulletin-v1")).toBeInTheDocument();
    expect(within(how).getByText("Petak berisiko tinggi", { exact: false })).toBeInTheDocument();
  });

  it("labels a template bulletin as template text and shows no Gemini chip", async () => {
    stubApi(
      handlers({
        ...BULLETIN,
        source: "template",
        model: null,
        prompt_version: "bulletin-template-v1",
      }),
    );

    renderApp("/public");

    expect(await screen.findByText("Teks templat")).toBeInTheDocument();
    expect(screen.queryByText("Buletin Gemini")).not.toBeInTheDocument();
    expect(screen.getByText(/Bukan Gemini yang menulis ini/)).toBeInTheDocument();
    expect(screen.queryByText("Model")).not.toBeInTheDocument();
  });

  it("says the bulletin is not written yet when none is stored", async () => {
    stubApi(
      handlers({
        ...BULLETIN,
        text_id: null,
        text_en: null,
        cited: [],
        source: null,
        model: null,
        prompt_version: null,
        created_at: null,
      }),
    );

    renderApp("/public");

    expect(await screen.findByText("Buletin minggu ini belum ditulis.")).toBeInTheDocument();
  });

  it("links the CSV and GeoJSON export for the shown week and names the license", async () => {
    stubApi(handlers());

    renderApp("/public");

    const csv = await screen.findByRole("link", { name: "Unduh CSV" });
    expect(csv).toHaveAttribute("href", "/api/public/riau/export.csv?week=2026-W42");
    expect(screen.getByRole("link", { name: "Unduh GeoJSON" })).toHaveAttribute(
      "href",
      "/api/public/riau/export.geojson?week=2026-W42",
    );
    expect(screen.getByRole("link", { name: "CC BY-NC-SA 4.0" })).toBeInTheDocument();
    expect(screen.getByText(/Copernicus Sentinel-1/)).toBeInTheDocument();
  });

  it("says there is no ranking for a week the API answers 404 for", async () => {
    stubApi({
      "GET /api/public/riau/summary?week=2026-W21": () =>
        Response.json({ detail: "no_rankings" }, { status: 404 }),
      "GET /api/public/riau/summary": () => Response.json(SUMMARY),
    });

    renderApp("/public?week=2026-W21");

    await waitFor(() =>
      expect(screen.getByText(/Belum ada peringkat untuk 2026-W21/)).toBeInTheDocument(),
    );
  });

  it("says there is no ranking yet when the latest week has none", async () => {
    stubApi({
      "GET /api/public/riau/summary": () =>
        Response.json({ detail: "no_rankings" }, { status: 404 }),
    });

    renderApp("/public");

    expect(await screen.findByText("Belum ada peringkat untuk wilayah ini.")).toBeInTheDocument();
  });

  it("shows the ranking-only note for Congo and no response record", async () => {
    stubApi({
      "GET /api/public/congo_cuvette/summary": () =>
        Response.json({ ...SUMMARY, region: "congo_cuvette" }),
      "GET /api/public/congo_cuvette/cells?limit=200": () =>
        Response.json({ ...CELLS, region: "congo_cuvette" }),
      "GET /api/public/riau/summary": () => Response.json(SUMMARY),
    });

    renderApp("/public?region=congo_cuvette");

    expect(await screen.findByText(/hanya menampilkan peringkat pengeringan/)).toBeInTheDocument();
    expect(await screen.findByText("Untuk sekarang buletin hanya untuk Riau.")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: /Catatan respons/ })).not.toBeInTheDocument();
    expect(screen.queryByText("Sekat kanal rusak")).not.toBeInTheDocument();
  });
});
