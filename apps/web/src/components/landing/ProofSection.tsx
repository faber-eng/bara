import { Link } from "@tanstack/react-router";
import evalJson from "../../eval/eval.json";
import type { LandingCopy } from "../../lib/copy/landing";
import type { CopyLanguage } from "../../lib/copy/language";
import type {
  AgentEval,
  DryingEval,
  EvalReport,
  FieldAccuracy,
  ReignitionEval,
} from "../../lib/eval/report";
import { parseEvalReport } from "../../lib/eval/report";
import { photoDamState } from "../../lib/landing/proof";
import { formatFixed, formatNumber, formatPercent } from "../../lib/public/format";
import { SectionHead } from "./SectionHead";

const TITLE_ID = "landing-proof-title";
const NO_VALUE = "n/a";
const PARSED = parseEvalReport(evalJson);

type ProofCopy = LandingCopy["proof"];
type PartProps<T> = { value: T; copy: ProofCopy; language: CopyLanguage };

function liftText(lift: number | null, language: CopyLanguage): string {
  if (lift === null) return NO_VALUE;
  return `${formatFixed(lift, 2, language)}x`;
}

function aucText(auc: number | null, language: CopyLanguage): string {
  if (auc === null) return NO_VALUE;
  return formatFixed(auc, 3, language);
}

function DryingPart({ value, copy, language }: PartProps<DryingEval>) {
  return (
    <div className="landing-proof-item landing-proof-drying">
      <h3 className="landing-h3">{copy.dryingTitle}</h3>
      <p>{copy.dryingBody(formatPercent(value.topShare, language))}</p>
      <table className="landing-lift">
        <thead>
          <tr>
            <th scope="col">{copy.year}</th>
            <th scope="col">{copy.lift}</th>
            <th scope="col">{copy.detectionWeeks}</th>
          </tr>
        </thead>
        <tbody>
          {value.years.map((year) => (
            <tr key={year.year}>
              <th scope="row">{year.year}</th>
              <td className="landing-lift-value">{liftText(year.lift, language)}</td>
              <td>{formatNumber(year.hotspots, language)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="landing-small">{copy.smallCount}</p>
    </div>
  );
}

function PhotoPart({ value, copy, language }: PartProps<FieldAccuracy>) {
  const accuracy = value.accuracy === null ? NO_VALUE : formatPercent(value.accuracy, language);
  return (
    <div className="landing-proof-item">
      <p className="landing-figure">{accuracy}</p>
      <h3 className="landing-h3">{copy.photoTitle}</h3>
      <p className="landing-small">{copy.photoSize(formatNumber(value.n, language))}</p>
    </div>
  );
}

function AgentPart({ value, copy, language }: PartProps<AgentEval>) {
  const cases = formatNumber(value.cases, language);
  return (
    <div className="landing-proof-item">
      <p className="landing-figure">
        {copy.agentValue(formatNumber(value.passed, language), cases)}
      </p>
      <h3 className="landing-h3">{copy.agentTitle}</h3>
      <p className="landing-small">{copy.agentSize(cases)}</p>
    </div>
  );
}

function ShortfallPart({ value, copy, language }: PartProps<ReignitionEval>) {
  const line = copy.reignition({
    modelAuc: aucText(value.model.auc, language),
    baselineAuc: aucText(value.baseline.auc, language),
    positives: formatNumber(value.positives, language),
    events: formatNumber(value.events, language),
  });
  return (
    <div className="landing-shortfall">
      <h3 className="landing-h3">{copy.shortTitle}</h3>
      <p>{line}</p>
    </div>
  );
}

type ProofLedgerProps = { report: EvalReport; copy: ProofCopy; language: CopyLanguage };

function ProofLedger({ report, copy, language }: ProofLedgerProps) {
  const damState = photoDamState(report.evidence);
  return (
    <>
      <div className="landing-proof-ledger">
        {report.drying && <DryingPart value={report.drying} copy={copy} language={language} />}
        {damState && <PhotoPart value={damState} copy={copy} language={language} />}
        {report.agent && <AgentPart value={report.agent} copy={copy} language={language} />}
      </div>
      {report.reignition && (
        <ShortfallPart value={report.reignition} copy={copy} language={language} />
      )}
    </>
  );
}

type ProofSectionProps = { copy: ProofCopy; language: CopyLanguage };

export function ProofSection({ copy, language }: ProofSectionProps) {
  return (
    <section className="landing-section landing-proof" aria-labelledby={TITLE_ID}>
      <div className="landing-wrap landing-proof-grid">
        <div className="landing-proof-intro">
          <SectionHead id={TITLE_ID} eyebrow={copy.eyebrow} title={copy.title} />
          <p className="landing-more">
            {copy.morePrefix}
            <Link to="/public" className="link">
              {copy.moreLink}
            </Link>
            {copy.moreSuffix}
          </p>
        </div>
        {PARSED.ok && <ProofLedger report={PARSED.report} copy={copy} language={language} />}
      </div>
    </section>
  );
}
