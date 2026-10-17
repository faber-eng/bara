import type { RankExplanation } from "../../lib/contracts";
import { type ExplanationSegment, segmentExplanation } from "../../lib/ops/citedNumbers";

function sourceTitle(fields: readonly string[]): string {
  return `Source field: ${fields.join(" or ")}`;
}

function SegmentView({ segment }: { segment: ExplanationSegment }) {
  if (segment.fields.length === 0) return <span>{segment.text}</span>;
  return (
    <span className="cited-number" title={sourceTitle(segment.fields)}>
      {segment.text}
    </span>
  );
}

export function ExplanationText({ explanation }: { explanation: RankExplanation }) {
  const segments = segmentExplanation(explanation.text, explanation.cited);
  const version = explanation.prompt_version ?? null;
  return (
    <>
      <span className="chip chip-gemini">Gemini</span>{" "}
      {segments.map((segment) => (
        <SegmentView key={segment.start} segment={segment} />
      ))}
      {version !== null && <span className="ops-meta"> ({version})</span>}
    </>
  );
}
