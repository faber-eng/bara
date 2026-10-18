import type { ExplanationPoint, RankExplanation } from "../../lib/contracts";
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

type CitedTextProps = { text: string; cited: RankExplanation["cited"] };

function CitedText({ text, cited }: CitedTextProps) {
  return segmentExplanation(text, cited).map((segment) => (
    <SegmentView key={segment.start} segment={segment} />
  ));
}

type PointItemProps = {
  point: ExplanationPoint;
  cited: RankExplanation["cited"];
  copy: DetailCopy;
};

function PointItem({ point, cited, copy }: PointItemProps) {
  return (
    <li className="explain-point">
      <span className={`explain-effect explain-effect-${point.effect}`}>
        {copy.cell.drivers.effects[point.effect]}
      </span>{" "}
      <CitedText text={point.text} cited={cited} />
    </li>
  );
}

type ExplanationTextProps = { explanation: RankExplanation; copy: DetailCopy };

export function ExplanationText({ explanation, copy }: ExplanationTextProps) {
  const points = explanation.points ?? [];
  if (points.length === 0) {
    return (
      <p className="mv-text">
        <span className="chip chip-gemini">Gemini</span>{" "}
        <CitedText text={explanation.text} cited={explanation.cited} />
      </p>
    );
  }
  return (
    <>
      <p className="mv-text">
        <span className="chip chip-gemini">Gemini</span>{" "}
        <CitedText text={explanation.summary ?? ""} cited={explanation.cited} />
      </p>
      <ul className="explain-points" aria-label={copy.cell.drivers.label}>
        {points.map((point) => (
          <PointItem key={point.field} point={point} cited={explanation.cited} copy={copy} />
        ))}
      </ul>
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
