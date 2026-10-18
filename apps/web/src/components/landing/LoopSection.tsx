import type { LandingCopy, LandingStep } from "../../lib/copy/landing";
import { SectionHead } from "./SectionHead";

const TITLE_ID = "landing-loop-title";

type StepRowProps = { step: LandingStep; number: number; copy: LandingCopy["loop"] };

function StepRow({ step, number, copy }: StepRowProps) {
  return (
    <li className="landing-step">
      <span className="landing-step-number" aria-hidden="true">
        {number}
      </span>
      <h3 className="landing-step-title">{step.title}</h3>
      <dl className="landing-step-split">
        <div>
          <dt>{copy.aiDoes}</dt>
          <dd>{step.ai}</dd>
        </div>
        <div>
          <dt>{copy.peopleDo}</dt>
          <dd>{step.people}</dd>
        </div>
      </dl>
    </li>
  );
}

export function LoopSection({ copy }: { copy: LandingCopy["loop"] }) {
  return (
    <section className="landing-section landing-loop on-dark" aria-labelledby={TITLE_ID}>
      <div className="landing-wrap">
        <SectionHead id={TITLE_ID} eyebrow={copy.eyebrow} title={copy.title} />
        <ol className="landing-steps" aria-label={copy.listLabel}>
          {copy.steps.map((step, index) => (
            <StepRow key={step.title} step={step} number={index + 1} copy={copy} />
          ))}
        </ol>
        <p className="landing-closing">{copy.closing}</p>
      </div>
    </section>
  );
}
