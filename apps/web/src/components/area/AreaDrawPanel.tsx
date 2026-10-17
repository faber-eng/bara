import type { DraftState } from "../../lib/area/polygon";
import { MAX_AREA_KM2 } from "../../lib/area/polygon";
import type { AreaCopy } from "../../lib/copy/area";

type AreaDrawPanelProps = {
  copy: AreaCopy;
  corners: number;
  km2: number;
  state: DraftState;
  pending: boolean;
  onUndo: () => void;
  onClear: () => void;
  onRank: () => void;
};

function draftNote(state: DraftState, copy: AreaCopy): string | null {
  if (state === "too_few") return copy.tooFew;
  if (state === "too_large") return copy.tooLarge(MAX_AREA_KM2);
  return null;
}

export function AreaDrawPanel({
  copy,
  corners,
  km2,
  state,
  pending,
  onUndo,
  onClear,
  onRank,
}: AreaDrawPanelProps) {
  const note = draftNote(state, copy);
  return (
    <div className="area-draw">
      <p className="field-hint">{copy.drawHint}</p>
      {corners > 0 && <p>{copy.drawn(corners, Math.round(km2))}</p>}
      {note !== null && <p role="status">{note}</p>}
      <div className="area-actions">
        <button
          type="button"
          className="btn btn-primary"
          disabled={state !== "ready" || pending}
          onClick={onRank}
        >
          {copy.rank}
        </button>
        <button
          type="button"
          className="btn btn-secondary btn-sm"
          disabled={corners === 0 || pending}
          onClick={onUndo}
        >
          {copy.undo}
        </button>
        <button
          type="button"
          className="btn btn-secondary btn-sm"
          disabled={corners === 0 || pending}
          onClick={onClear}
        >
          {copy.clear}
        </button>
      </div>
    </div>
  );
}
