import { useState } from "react";
import type { GeoPoint } from "../../lib/contracts";
import type { JoinCopy } from "../../lib/copy/join";
import {
  formatCoordinate,
  type LocationReason,
  LocationUnavailableError,
  readDeviceLocation,
} from "../../lib/geo";
import { HomeMap, readMapsKey } from "./HomeMap";

type LocationState = "idle" | "locating" | LocationReason;

function stateAfterFailure(error: unknown): LocationState {
  if (error instanceof LocationUnavailableError) return error.reason;
  return "unavailable";
}

type HomePickerProps = {
  copy: JoinCopy;
  value: GeoPoint | null;
  invalid: boolean;
  onChange: (point: GeoPoint) => void;
};

type LocationNoteProps = { copy: JoinCopy; state: LocationState; hasMap: boolean };

function LocationNote({ copy, state, hasMap }: LocationNoteProps) {
  if (state === "locating") return <p role="status">{copy.homeLocating}</p>;
  if (state === "denied")
    return <p role="alert">{hasMap ? copy.homeDenied : copy.homeDeniedNoMap}</p>;
  if (state === "unsupported") return <p role="alert">{copy.homeUnsupported}</p>;
  if (state === "unavailable") return <p role="alert">{copy.homeUnavailable}</p>;
  return null;
}

export function HomePicker({ copy, value, invalid, onChange }: HomePickerProps) {
  const [state, setState] = useState<LocationState>("idle");
  const hasMap = readMapsKey() !== "";

  async function pickDeviceLocation() {
    setState("locating");
    try {
      onChange(await readDeviceLocation());
      setState("idle");
    } catch (error) {
      setState(stateAfterFailure(error));
    }
  }

  return (
    <div className="join-home" aria-invalid={invalid}>
      <button
        type="button"
        className="btn btn-secondary btn-sm"
        disabled={state === "locating"}
        onClick={() => void pickDeviceLocation()}
      >
        {copy.homeGps}
      </button>
      <LocationNote copy={copy} state={state} hasMap={hasMap} />
      {value !== null && (
        <p className="field-hint">
          {copy.homeChosen(formatCoordinate(value.lat), formatCoordinate(value.lon))}
        </p>
      )}
      <p className="field-hint">{hasMap ? copy.homeMapNote : copy.homeMapMissing}</p>
      {hasMap && <HomeMap value={value} onPick={onChange} />}
    </div>
  );
}
