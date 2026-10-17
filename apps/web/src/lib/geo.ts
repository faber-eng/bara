import type { GeoPoint } from "./contracts";

export type LocationReason = "unsupported" | "denied" | "unavailable";

export class LocationUnavailableError extends Error {
  override name = "LocationUnavailableError";
  readonly reason: LocationReason;

  constructor(reason: LocationReason) {
    super(`Location is ${reason}`);
    this.reason = reason;
  }
}

const LOCATION_TIMEOUT_MS = 10_000;

function reasonFor(error: GeolocationPositionError): LocationReason {
  return error.code === error.PERMISSION_DENIED ? "denied" : "unavailable";
}

export function readDeviceLocation(): Promise<GeoPoint> {
  return new Promise((resolve, reject) => {
    if (!("geolocation" in navigator)) {
      reject(new LocationUnavailableError("unsupported"));
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (position) => resolve({ lat: position.coords.latitude, lon: position.coords.longitude }),
      (error) => reject(new LocationUnavailableError(reasonFor(error))),
      { enableHighAccuracy: true, timeout: LOCATION_TIMEOUT_MS },
    );
  });
}

export function formatCoordinate(value: number): string {
  return value.toFixed(5);
}
