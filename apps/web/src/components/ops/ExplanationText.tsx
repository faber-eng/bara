import type { RankExplanation } from "../../lib/contracts";
import type { DetailCopy } from "../../lib/copy/detail";
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
  return (
    <>
      <span className="chip chip-gemini">Gemini</span>{" "}
      {segments.map((segment) => (
        <SegmentView key={segment.start} segment={segment} />
      ))}
    </>
  );
}

type ExplanationHowProps = { explanation: RankExplanation; copy: DetailCopy };

export function ExplanationHow({ explanation, copy }: ExplanationHowProps) {
  const version = explanation.prompt_version ?? null;
  return (
    <details className="pub-how">
      <summary>{copy.cell.how.title}</summary>
      <dl className="pub-how-facts">
        <div>
          <dt>{copy.cell.how.model}</dt>
          <dd className="spec-code">Gemini</dd>
        </div>
        {version !== null && (
          <div>
            <dt>{copy.cell.how.promptVersion}</dt>
            <dd className="spec-code">{version}</dd>
          </div>
        )}
      </dl>
    </details>
  );
}
