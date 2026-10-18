import { useId, useState } from "react";
import type { GeoPoint } from "../../lib/contracts";
import type { JoinCopy } from "../../lib/copy/join";
import {
  formatCoordinate,
  type LocationReason,
  LocationUnavailableError,
  readDeviceLocation,
} from "../../lib/geo";
import { parseCoordinates } from "../../lib/join/coordinates";
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

type PasteFieldProps = { copy: JoinCopy; onChange: (point: GeoPoint) => void };

function PasteField({ copy, onChange }: PasteFieldProps) {
  const id = useId();
  const [text, setText] = useState("");
  const point = parseCoordinates(text);
  const rejected = text.trim() !== "" && point === null;

  function handleInput(next: string) {
    setText(next);
    const parsed = parseCoordinates(next);
    if (parsed !== null) onChange(parsed);
  }

  return (
    <div className="home-paste">
      <label className="field-hint" htmlFor={id}>
        {copy.homePaste}
      </label>
      <input
        id={id}
        className="input"
        type="text"
        inputMode="decimal"
        autoComplete="off"
        placeholder={copy.homePasteHint}
        value={text}
        aria-invalid={rejected}
        onChange={(event) => handleInput(event.target.value)}
      />
      {rejected && <p role="alert">{copy.homePasteError}</p>}
    </div>
  );
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
      <PasteField copy={copy} onChange={onChange} />
      <p className="field-hint">{hasMap ? copy.homeMapNote : copy.homeMapMissing}</p>
      {hasMap && <HomeMap value={value} onPick={onChange} />}
      {value !== null && (
        <p className="field-hint" role="status">
          {copy.homeChosen(formatCoordinate(value.lat), formatCoordinate(value.lon))}
        </p>
      )}
    </div>
  );
}
