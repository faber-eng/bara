import { act, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MiniMap } from "./MiniMap";

const mapMounts = vi.hoisted(() => ({ count: 0 }));
const providerProps = vi.hoisted(() => ({ onError: null as ((error: unknown) => void) | null }));

vi.mock("@vis.gl/react-google-maps", async () => {
  const { useEffect } = await import("react");
  return {
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
    Map: ({
      children,
      mapTypeId,
      defaultZoom,
    }: {
      children: ReactNode;
      mapTypeId: string;
      defaultZoom: number;
    }) => {
      useEffect(() => {
        mapMounts.count += 1;
      }, []);
      return (
        <div data-testid="map" data-type={mapTypeId} data-zoom={defaultZoom}>
          {children}
        </div>
      );
    },
    Marker: ({ position }: { position: { lat: number; lng: number } }) => (
      <div data-testid="marker" data-lat={position.lat} data-lng={position.lng} />
    ),
  };
});

const URL_WITH_POINT = "https://www.google.com/maps/search/?api=1&query=0.5123,102.4567";

describe("MiniMap", () => {
  beforeEach(() => {
    vi.stubEnv("VITE_MAPS_KEY", "test-key");
    mapMounts.count = 0;
  });

  it("draws a hybrid map with a marker at the escalation point", () => {
    render(<MiniMap mapUrl={URL_WITH_POINT} />);
    expect(screen.getByTestId("map")).toHaveAttribute("data-type", "hybrid");
    expect(screen.getByTestId("map")).toHaveAttribute("data-zoom", "13");
    expect(screen.getByTestId("marker")).toHaveAttribute("data-lat", "0.5123");
    expect(screen.getByTestId("marker")).toHaveAttribute("data-lng", "102.4567");
    expect(screen.getByText("0.5123, 102.4567")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open in Google Maps" })).toHaveAttribute(
      "href",
      URL_WITH_POINT,
    );
  });

  it("keeps one map instance across re-renders", () => {
    const { rerender } = render(<MiniMap mapUrl={URL_WITH_POINT} />);
    rerender(<MiniMap mapUrl={URL_WITH_POINT} />);
    expect(mapMounts.count).toBe(1);
  });

  it("shows the neutral box when no Maps key is configured", () => {
    vi.stubEnv("VITE_MAPS_KEY", "");
    render(<MiniMap mapUrl={URL_WITH_POINT} />);
    expect(screen.queryByTestId("map")).not.toBeInTheDocument();
    expect(screen.getByText("0.5123, 102.4567")).toBeInTheDocument();
  });

  it("shows a neutral box and no map when the point is missing", () => {
    render(<MiniMap mapUrl="https://www.google.com/maps" />);
    expect(screen.queryByTestId("map")).not.toBeInTheDocument();
    expect(screen.getByText("Map not available")).toBeInTheDocument();
  });

  it("falls back to the neutral box when Maps fails to load", () => {
    render(<MiniMap mapUrl={URL_WITH_POINT} />);
    act(() => providerProps.onError?.(new Error("blocked")));
    expect(screen.getByText("Map not available")).toBeInTheDocument();
    expect(screen.queryByTestId("map")).not.toBeInTheDocument();
    expect(screen.getByText("0.5123, 102.4567")).toBeInTheDocument();
  });
});
