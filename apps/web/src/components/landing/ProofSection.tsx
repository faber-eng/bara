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
    <div className="card landing-drying">
      <h3 className="landing-h3">{copy.dryingTitle}</h3>
      <p className="muted">{copy.dryingBody(formatPercent(value.topShare, language))}</p>
      <table className="table landing-lift">
        <thead>
          <tr>
            <th scope="col">{copy.year}</th>
            <th scope="col" className="num">
              {copy.lift}
            </th>
            <th scope="col" className="num">
              {copy.detectionWeeks}
            </th>
          </tr>
        </thead>
        <tbody>
          {value.years.map((year) => (
            <tr key={year.year}>
              <th scope="row">{year.year}</th>
              <td className="num landing-lift-value">{liftText(year.lift, language)}</td>
              <td className="num">{formatNumber(year.hotspots, language)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="muted landing-note">{copy.smallCount}</p>
    </div>
  );
}

function PhotoPart({ value, copy, language }: PartProps<FieldAccuracy>) {
  const accuracy = value.accuracy === null ? NO_VALUE : formatPercent(value.accuracy, language);
  return (
    <div className="landing-figure-block">
      <p className="serif num landing-figure">{accuracy}</p>
      <h3 className="landing-h3">{copy.photoTitle}</h3>
      <p>
        <span className="chip chip-example num">
          {copy.photoSize(formatNumber(value.n, language))}
        </span>
      </p>
    </div>
  );
}

function AgentPart({ value, copy, language }: PartProps<AgentEval>) {
  const cases = formatNumber(value.cases, language);
  return (
    <div className="landing-figure-block">
      <p className="serif num landing-figure">
        {copy.agentValue(formatNumber(value.passed, language), cases)}
      </p>
      <h3 className="landing-h3">{copy.agentTitle}</h3>
      <p className="muted">{copy.agentSize(cases)}</p>
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
    <div className="tile tile-peach landing-shortfall">
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
        <div className="landing-figures">
          {damState && <PhotoPart value={damState} copy={copy} language={language} />}
          {report.agent && <AgentPart value={report.agent} copy={copy} language={language} />}
        </div>
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
    <section className="landing-proof" aria-labelledby={TITLE_ID}>
      <div className="wrap">
        <h2 id={TITLE_ID} className="section-title landing-title">
          {copy.title}
        </h2>
        {PARSED.ok && <ProofLedger report={PARSED.report} copy={copy} language={language} />}
        <p className="muted landing-more">
          {copy.morePrefix}
          <Link to="/public" className="link">
            {copy.moreLink}
          </Link>
          {copy.moreSuffix}
        </p>
      </div>
    </section>
  );
}
