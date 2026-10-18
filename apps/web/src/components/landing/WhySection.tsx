import type { LandingCopy } from "../../lib/copy/landing";

const TITLE_ID = "landing-why-title";

export function WhySection({ copy }: { copy: LandingCopy["why"] }) {
  return (
    <section className="band landing-why" aria-labelledby={TITLE_ID}>
      <div className="wrap landing-why-grid">
        <h2 id={TITLE_ID} className="section-title landing-title">
          {copy.title}
        </h2>
        <div className="landing-why-text">
          {copy.paragraphs.map((paragraph) => (
            <p key={paragraph}>{paragraph}</p>
          ))}
        </div>
      </div>
    </section>
  );
}
