import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { setCopyLanguage } from "../../lib/copy/language";
import { volunteerCopy } from "../../lib/copy/volunteer";
import { HomeLocation } from "./HomeLocation";

const api = vi.hoisted(() => ({ saveHome: vi.fn() }));

vi.mock("../../lib/api/volunteer", () => api);
vi.mock("../join/HomeMap", () => ({
  readMapsKey: () => "key",
  HomeMap: ({ onPick }: { onPick: (point: { lat: number; lon: number }) => void }) => (
    <button type="button" onClick={() => onPick({ lat: 0.7999, lon: 102.47081 })}>
      map
    </button>
  ),
}));
vi.mock("../brigade/MiniMap", () => ({ MiniMap: () => <div /> }));

const HOME = { lat: 0.5, lon: 101.4 };

function renderEditor() {
  const client = new QueryClient();
  const invalidate = vi.spyOn(client, "invalidateQueries");
  render(
    <QueryClientProvider client={client}>
      <HomeLocation
        copy={volunteerCopy("en")}
        volunteerId="v1"
        home={HOME}
        name="Sari"
        volunteerRole="volunteer"
      />
    </QueryClientProvider>,
  );
  fireEvent.click(screen.getByText("My home location"));
  fireEvent.click(screen.getByRole("button", { name: "Change" }));
  return invalidate;
}

describe("HomeLocation change", () => {
  beforeEach(() => {
    setCopyLanguage("en");
    api.saveHome.mockReset();
  });

  it("shows the pin feedback after a map click and saves the pin", async () => {
    api.saveHome.mockResolvedValue({ lat: 0.7999, lon: 102.47081 });
    const invalidate = renderEditor();
    expect(screen.getByRole("button", { name: "Save this as my home" })).toBeDisabled();

    fireEvent.click(screen.getByRole("button", { name: "map" }));
    expect(screen.getByText("Pin set: 0.79990, 102.47081")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Save this as my home" }));
    expect(await screen.findByText("Saved as your home.")).toBeInTheDocument();
    expect(api.saveHome).toHaveBeenCalledWith("v1", { lat: 0.7999, lon: 102.47081 });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["inbox", "v1"] });
  });

  it("moves the pin from a pasted lat, lon", () => {
    renderEditor();
    fireEvent.change(screen.getByLabelText("Paste coordinates"), {
      target: { value: "0.79990, 102.47081" },
    });
    expect(screen.getByText("Pin set: 0.79990, 102.47081")).toBeInTheDocument();
  });

  it("rejects a pasted point that is out of range", () => {
    renderEditor();
    fireEvent.change(screen.getByLabelText("Paste coordinates"), { target: { value: "95, 10" } });
    expect(screen.getByRole("alert")).toHaveTextContent("Write latitude, longitude");
    expect(screen.queryByText(/Pin set/)).not.toBeInTheDocument();
  });

  it("shows the error when saving fails", async () => {
    api.saveHome.mockRejectedValue(new Error("boom"));
    renderEditor();
    fireEvent.click(screen.getByRole("button", { name: "map" }));
    fireEvent.click(screen.getByRole("button", { name: "Save this as my home" }));
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("did not save"));
  });
});
