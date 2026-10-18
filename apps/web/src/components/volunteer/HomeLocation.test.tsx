import { act, fireEvent, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { volunteerCopy } from "../../lib/copy/volunteer";
import { HomeLocation } from "./HomeLocation";

const providerProps = vi.hoisted(() => ({ onError: null as ((error: unknown) => void) | null }));

vi.mock("@vis.gl/react-google-maps", () => ({
  APIProvider: ({
    children,
    onError,
  }: {
    children: ReactNode;
    onError: (error: unknown) => void;
  }) => {
    providerProps.onError = onError;
    return <div>{children}</div>;
  },
  Map: ({ children }: { children: ReactNode }) => <div data-testid="map">{children}</div>,
  Marker: ({ position }: { position: { lat: number; lng: number } }) => (
    <div data-testid="marker" data-lat={position.lat} data-lng={position.lng} />
  ),
}));

const HOME = { lat: 0.51234, lon: 101.44567 };

function renderHome(language: "en" | "id" = "en") {
  const copy = volunteerCopy(language);
  render(
    <HomeLocation copy={copy} volunteerId="v1" home={HOME} name="Sari" volunteerRole="volunteer" />,
  );
}

describe("HomeLocation", () => {
  beforeEach(() => {
    vi.stubEnv("VITE_MAPS_KEY", "test-key");
  });

  it("loads no map until the item is opened", () => {
    renderHome();
    expect(screen.getByText("My home location")).toBeInTheDocument();
    expect(screen.queryByTestId("map")).not.toBeInTheDocument();
    expect(screen.queryByText("0.51234, 101.44567")).not.toBeInTheDocument();
  });

  it("shows the pin, five-decimal coordinates, name and role once opened", () => {
    renderHome();
    fireEvent.click(screen.getByText("My home location"));
    expect(screen.getByTestId("marker")).toHaveAttribute("data-lat", "0.51234");
    expect(screen.getByTestId("marker")).toHaveAttribute("data-lng", "101.44567");
    expect(screen.getByText("0.51234, 101.44567")).toBeInTheDocument();
    expect(screen.getByText("Sari, Volunteer")).toBeInTheDocument();
  });

  it("keeps the coordinates and the Google Maps link when the map fails", () => {
    renderHome();
    fireEvent.click(screen.getByText("My home location"));
    act(() => providerProps.onError?.(new Error("blocked")));
    expect(screen.queryByTestId("map")).not.toBeInTheDocument();
    expect(screen.getByText("0.51234, 101.44567")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open in Google Maps" })).toHaveAttribute(
      "href",
      "https://www.google.com/maps/search/?api=1&query=0.51234,101.44567",
    );
  });

  it("speaks Indonesian", () => {
    renderHome("id");
    fireEvent.click(screen.getByText("Lokasi rumah saya"));
    expect(screen.getByText("Sari, Relawan")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Buka di Google Maps" })).toBeInTheDocument();
  });

  it("renders nothing without a home point", () => {
    const copy = volunteerCopy("en");
    const { container } = render(
      <HomeLocation copy={copy} volunteerId="v1" home={null} name={null} volunteerRole={null} />,
    );
    expect(container).toBeEmptyDOMElement();
  });
});
