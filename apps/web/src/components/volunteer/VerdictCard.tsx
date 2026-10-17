import type { Evidence } from "../../lib/contracts";
import type { CopyLanguage } from "../../lib/copy/language";
import type { VolunteerCopy } from "../../lib/copy/volunteer";
import { describeVerdict } from "../../lib/volunteer/verdictText";
import { SampleBadge } from "./FlowPanels";

type VerdictCardProps = {
  copy: VolunteerCopy;
  language: CopyLanguage;
  evidence: Evidence;
  onDone: () => void;
};

export function VerdictCard({ copy, language, evidence, onDone }: VerdictCardProps) {
  if (evidence.verdict === null) return null;
  const view = describeVerdict(evidence, evidence.verdict, copy, language);
  return (
    <section className="card flow-panel" aria-label={view.headline}>
      <div className="proto-row">
        <span className="chip chip-gemini">{copy.geminiChip}</span>
        {view.sample && <SampleBadge copy={copy} />}
        {view.needsHuman && <span className="chip chip-human-review">{copy.needsHumanChip}</span>}
      </div>
      <h3 className="verdict-headline">{view.headline}</h3>
      <dl className="verdict-rows">
        {view.rows.map((row) => (
          <div key={row.label} className="verdict-row">
            <dt>{row.label}</dt>
            <dd>{row.value}</dd>
          </div>
        ))}
      </dl>
      {view.reasons.length > 0 && (
        <details>
          <summary>{copy.why}</summary>
          <ul>
            {view.reasons.map((reason, index) => (
              // biome-ignore lint/suspicious/noArrayIndexKey: the reasons never reorder and may repeat
              <li key={`${index}-${reason}`}>{reason}</li>
            ))}
          </ul>
        </details>
      )}
      <p>{view.next}</p>
      <button type="button" className="btn btn-secondary btn-block" onClick={onDone}>
        {copy.sendAnother}
      </button>
    </section>
  );
}
