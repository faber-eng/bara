import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { detailCopy } from "../../lib/copy/detail";
import { DAM_STATES, damColor } from "../../lib/ops/cellLayer";
import { MapKey } from "./MapKey";

const copy = detailCopy("en");

function swatchColors(root: HTMLElement): string[] {
  return Array.from(root.querySelectorAll<HTMLElement>(".mv-swatch-dot")).map(
    (swatch) => swatch.style.background,
  );
}

function toRgb(hex: string): string {
  const value = Number.parseInt(hex.slice(1), 16);
  return `rgb(${(value >> 16) & 255}, ${(value >> 8) & 255}, ${value & 255})`;
}

describe("MapKey", () => {
  it("names a colour for every dam state the map can draw, purple and grey included", () => {
    render(<MapKey marks={["cell", "dam", "case"]} copy={copy} screen="ops" />);

    const key = screen.getByRole("region", { name: "Map key" });
    const colors = swatchColors(key).map((color) => color.toLowerCase());
    for (const state of DAM_STATES) {
      const color = damColor(state).toLowerCase();
      expect(colors.some((shown) => shown === color || shown === toRgb(color))).toBe(true);
    }
    for (const label of ["Intact", "Damaged", "Broken", "Water over the top", "Not checked"]) {
      expect(within(key).getByText(label)).toBeInTheDocument();
    }
    expect(within(key).getAllByText("Not checked")).toHaveLength(1);
    expect(key).toHaveTextContent("Square = a 1 km peat area.");
    expect(key).toHaveTextContent("Circle = a canal dam.");
    expect(key).toHaveTextContent("Dark outline = open case");
  });

  it("shows only the marks its map draws", () => {
    render(<MapKey marks={["areaShape", "areaCell"]} copy={copy} screen="area" />);

    const key = screen.getByRole("region", { name: "Map key" });
    expect(key).toHaveTextContent("Brown outline = the area you drew.");
    expect(key).toHaveTextContent("Circle = a ranked peat cell inside the area you drew.");
    expect(within(key).queryByText("Broken")).not.toBeInTheDocument();
    expect(key).not.toHaveTextContent("Square =");
  });

  it("adds a layer row only for a layer that is on", () => {
    render(<MapKey marks={["cell", "burnScar"]} copy={copy} screen="public" />);

    const key = screen.getByRole("region", { name: "Map key" });
    expect(key).toHaveTextContent("Dark brown = burned area seen from satellite.");
    expect(key).not.toHaveTextContent("Re-ignition risk");
    expect(key).not.toHaveTextContent("Peat map");
  });

  it("explains the screen behind a 'What am I looking at?' toggle", () => {
    render(<MapKey marks={["cell"]} copy={copy} screen="public" />);

    const toggle = screen.getByText("What am I looking at?");
    const details = toggle.closest("details") as HTMLDetailsElement;
    expect(details.open).toBe(false);
    fireEvent.click(toggle);

    expect(details).toHaveTextContent("Click a square or a dam for details.");
  });

  it("speaks Indonesian when asked", () => {
    render(<MapKey marks={["dam"]} copy={detailCopy("id")} screen="public" />);

    const key = screen.getByRole("region", { name: "Keterangan peta" });
    expect(within(key).getByText("Jebol")).toBeInTheDocument();
    expect(within(key).getByText("Air melimpas")).toBeInTheDocument();
    expect(screen.getByText("Ini peta apa?")).toBeInTheDocument();
  });
});
