import { fireEvent, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { setCopyLanguage } from "../../lib/copy/language";
import { renderApp, stubApi } from "../../test-utils";

vi.mock("../../lib/auth", () => ({ getIdToken: vi.fn().mockResolvedValue("token-1") }));

const areaItem = {
  id: "riau-area-1",
  kind: "area",
  label: "Riau area 1",
  credit: "Faber Fathers, CC BY 4.0",
  url: "/api/samples/riau-area-1/file",
};

const geojson = {
  type: "FeatureCollection",
  features: [
    {
      type: "Feature",
      properties: { name: "Riau area 1" },
      geometry: {
        type: "Polygon",
        coordinates: [
          [
            [102.1, 0.55],
            [102.18, 0.55],
            [102.18, 0.62],
            [102.1, 0.62],
            [102.1, 0.55],
          ],
        ],
      },
    },
  ],
};

describe("area screen sample", () => {
  beforeEach(() => setCopyLanguage("id"));
  afterEach(() => vi.unstubAllGlobals());

  it("loads a sample area and marks it as a sample", async () => {
    stubApi({
      "GET /api/samples?kind=area": () => Response.json([areaItem]),
      [`GET ${areaItem.url}`]: () => Response.json(geojson),
    });
    renderApp("/area/new");

    fireEvent.click(await screen.findByRole("button", { name: "Pakai contoh" }));
    fireEvent.click(await screen.findByRole("button", { name: /Riau area 1/ }));

    expect(await screen.findByRole("heading", { name: "Riau area 1" })).toBeInTheDocument();
    expect(screen.getByText("4 titik sudut")).toBeInTheDocument();
    expect(screen.getByText("Sampel")).toBeInTheDocument();
  });

  it("says plainly when the sample list fails and offers a retry", async () => {
    stubApi({ "GET /api/samples?kind=area": () => new Response("x", { status: 500 }) });
    renderApp("/area/new");

    fireEvent.click(await screen.findByRole("button", { name: "Pakai contoh" }));

    expect(await screen.findByText("Contoh tidak termuat. Coba lagi.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Coba lagi" })).toBeInTheDocument();
  });

  it("says plainly when the file is not an area", async () => {
    stubApi({
      "GET /api/samples?kind=area": () => Response.json([areaItem]),
      [`GET ${areaItem.url}`]: () => Response.json({ type: "FeatureCollection", features: [] }),
    });
    renderApp("/area/new");

    fireEvent.click(await screen.findByRole("button", { name: "Pakai contoh" }));
    fireEvent.click(await screen.findByRole("button", { name: /Riau area 1/ }));

    expect(await screen.findByRole("alert")).toHaveTextContent("tidak bisa dibaca");
  });
});
