import { afterEach, describe, expect, it, vi } from "vitest";
import { formatCoordinate, LocationUnavailableError, readDeviceLocation } from "./geo";

function stubGeolocation(getCurrentPosition: Geolocation["getCurrentPosition"]) {
  vi.stubGlobal("navigator", { geolocation: { getCurrentPosition } });
}

describe("readDeviceLocation", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("resolves the device position as a GeoPoint", async () => {
    stubGeolocation((onSuccess) =>
      onSuccess({ coords: { latitude: 0.5, longitude: 101.4 } } as GeolocationPosition),
    );

    await expect(readDeviceLocation()).resolves.toEqual({ lat: 0.5, lon: 101.4 });
  });

  it("rejects as denied when the browser refuses", async () => {
    stubGeolocation((_ok, onError) =>
      onError?.({ code: 1, PERMISSION_DENIED: 1 } as GeolocationPositionError),
    );

    await expect(readDeviceLocation()).rejects.toMatchObject({ reason: "denied" });
  });

  it("rejects as unavailable on a timeout", async () => {
    stubGeolocation((_ok, onError) =>
      onError?.({ code: 3, PERMISSION_DENIED: 1 } as GeolocationPositionError),
    );

    await expect(readDeviceLocation()).rejects.toMatchObject({ reason: "unavailable" });
  });

  it("rejects as unsupported without geolocation", async () => {
    vi.stubGlobal("navigator", {});

    const error = await readDeviceLocation().catch((caught: unknown) => caught);

    expect(error).toBeInstanceOf(LocationUnavailableError);
    expect(error).toMatchObject({ reason: "unsupported" });
  });
});

describe("formatCoordinate", () => {
  it("keeps five decimals", () => {
    expect(formatCoordinate(0.5)).toBe("0.50000");
  });
});
