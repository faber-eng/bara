import type { LandingCopy, LandingMoment } from "../../lib/copy/landing";
import { SectionHead } from "./SectionHead";

const TITLE_ID = "landing-moments-title";

function Moment({ moment }: { moment: LandingMoment }) {
  return (
    <article className="landing-moment">
      <h3 className="landing-h3">{moment.when}</h3>
      <p className="landing-moment-flow">
        <span>{moment.signal}</span>
        <span aria-hidden="true" className="landing-moment-arrow">
          →
        </span>
        <span>{moment.action}</span>
      </p>
      <p>{moment.body}</p>
    </article>
  );
}

export function MomentsSection({ copy }: { copy: LandingCopy["moments"] }) {
  return (
    <section className="landing-section landing-moments" aria-labelledby={TITLE_ID}>
      <div className="landing-wrap">
        <SectionHead id={TITLE_ID} eyebrow={copy.eyebrow} title={copy.title} />
        <div className="landing-moments-pair">
          <Moment moment={copy.before} />
          <Moment moment={copy.after} />
        </div>
      </div>
    </section>
  );
}
