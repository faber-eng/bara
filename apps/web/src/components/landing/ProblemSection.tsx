import type { LandingCopy } from "../../lib/copy/landing";
import { DamDiagram } from "./DamDiagram";

const TITLE_ID = "landing-problem-title";

export function ProblemSection({ copy }: { copy: LandingCopy["problem"] }) {
  return (
    <section className="landing-problem" aria-labelledby={TITLE_ID}>
      <div className="wrap landing-problem-grid">
        <div className="landing-problem-text">
          <h2 id={TITLE_ID} className="section-title landing-title">
            {copy.title}
          </h2>
          {copy.paragraphs.map((paragraph) => (
            <p key={paragraph} className="landing-prose">
              {paragraph}
            </p>
          ))}
        </div>
        <DamDiagram copy={copy.diagram} />
      </div>
    </section>
  );
}
