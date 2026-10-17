import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { fetchSamples } from "../../lib/api/samples";
import type { SampleItem, SampleKind } from "../../lib/contracts";
import type { SamplePickerCopy } from "../../lib/copy/samples";

const SAMPLES_STALE_MS = 5 * 60_000;

type SamplePickerProps = {
  kind: SampleKind;
  copy: SamplePickerCopy;
  disabled?: boolean;
  onPick: (item: SampleItem) => void;
};

function SampleList({ kind, copy, disabled, onPick }: Required<SamplePickerProps>) {
  const samples = useQuery({
    queryKey: ["samples", kind],
    queryFn: ({ signal }) => fetchSamples(kind, signal),
    staleTime: SAMPLES_STALE_MS,
    retry: false,
  });

  if (samples.isPending) return <p role="status">{copy.sampleLoading}</p>;
  if (samples.isError) {
    return (
      <div role="alert">
        <p>{copy.sampleFailed}</p>
        <button
          type="button"
          className="btn btn-secondary btn-sm"
          onClick={() => void samples.refetch()}
        >
          {copy.retry}
        </button>
      </div>
    );
  }
  const matching = samples.data.filter((item) => item.kind === kind);
  if (matching.length === 0) return <p>{copy.sampleEmpty}</p>;
  return (
    <ul className="sample-list" aria-label={copy.sampleTitle}>
      {matching.map((item) => (
        <li key={item.id}>
          <button
            type="button"
            className="sample-item"
            disabled={disabled}
            onClick={() => onPick(item)}
          >
            <span>{item.label}</span>
            <span className="field-hint">{item.credit}</span>
          </button>
        </li>
      ))}
    </ul>
  );
}

export function SamplePicker({ kind, copy, disabled = false, onPick }: SamplePickerProps) {
  const [open, setOpen] = useState(false);

  function handlePick(item: SampleItem) {
    setOpen(false);
    onPick(item);
  }

  return (
    <div className="sample-picker">
      <button
        type="button"
        className="btn btn-secondary btn-sm"
        aria-expanded={open}
        disabled={disabled}
        onClick={() => setOpen((previous) => !previous)}
      >
        {copy.useSample}
      </button>
      {open && <SampleList kind={kind} copy={copy} disabled={disabled} onPick={handlePick} />}
    </div>
  );
}
