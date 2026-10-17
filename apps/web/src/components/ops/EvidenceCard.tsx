import type { Evidence, Verdict } from "../../lib/contracts";
import { confidenceLabel, evidenceImageUrl, spaced } from "../../lib/ops/caseDrawer";

function Thumbnail({ evidence }: { evidence: Evidence }) {
  const url = evidenceImageUrl(evidence.gcs_uri);
  if (evidence.kind === "photo" && url !== null) {
    return <img className="thumb" src={url} alt={`Evidence ${evidence.id}`} loading="lazy" />;
  }
  return <span className="thumb thumb-empty">{spaced(evidence.kind)}</span>;
}

function VerdictFields({ verdict }: { verdict: Verdict }) {
  return (
    <dl className="verdict">
      <dt>Subject</dt>
      <dd>{spaced(verdict.subject)}</dd>
      <dt>Dam state</dt>
      <dd>{spaced(verdict.dam_state)}</dd>
      <dt>Smoke</dt>
      <dd>{verdict.smoke}</dd>
      <dt>Hot ground</dt>
      <dd>{verdict.hot_ground_signs}</dd>
      <dt>Open flame</dt>
      <dd>{verdict.open_flame}</dd>
      {verdict.transcript_en !== null && (
        <>
          <dt>Voice note</dt>
          <dd>{verdict.transcript_en}</dd>
        </>
      )}
      <dt>Reasons</dt>
      <dd>{verdict.reasons.join("; ")}</dd>
    </dl>
  );
}

type VerdictHeadProps = { verdict: Verdict; canExplain: boolean; onWhy: () => void };

function VerdictHead({ verdict, canExplain, onWhy }: VerdictHeadProps) {
  return (
    <div className="verdict-head">
      <span className="chip chip-gemini">Gemini</span>
      <span>Confidence {confidenceLabel(verdict.confidence)}</span>
      {verdict.needs_human && <span className="chip chip-human-review">Needs a person</span>}
      {canExplain && (
        <button type="button" className="btn btn-quiet btn-sm" onClick={onWhy}>
          Why?
        </button>
      )}
    </div>
  );
}

function locationLabel(locationOk: boolean | null): string | null {
  if (locationOk === null) return null;
  return locationOk ? "Location matches the task" : "Location is off the task";
}

type EvidenceCardProps = { evidence: Evidence; canExplain: boolean; onWhy: () => void };

export function EvidenceCard({ evidence, canExplain, onWhy }: EvidenceCardProps) {
  const location = locationLabel(evidence.location_ok);
  return (
    <li className="evidence-card">
      <Thumbnail evidence={evidence} />
      <div className="evidence-body">
        <p className="ops-meta">
          {spaced(evidence.kind)} from {evidence.uploaded_by}
          {evidence.sample && <span className="chip chip-plain">Sample</span>}
        </p>
        {location !== null && <p className="ops-meta">{location}</p>}
        {evidence.verdict === null ? (
          <p className="ops-meta">No verdict yet.</p>
        ) : (
          <>
            <VerdictHead verdict={evidence.verdict} canExplain={canExplain} onWhy={onWhy} />
            <VerdictFields verdict={evidence.verdict} />
          </>
        )}
      </div>
    </li>
  );
}
