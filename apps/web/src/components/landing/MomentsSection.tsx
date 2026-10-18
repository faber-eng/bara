import type { LandingCopy, LandingMoment } from "../../lib/copy/landing";

const TITLE_ID = "landing-moments-title";

type MomentProps = { moment: LandingMoment; tone: "tile-sage" | "tile-peach" };

function Moment({ moment, tone }: MomentProps) {
  return (
    <article className={`tile ${tone} landing-moment`}>
      <h3 className="serif landing-moment-title">{moment.when}</h3>
      <p className="landing-chips">
        <span className="chip chip-plain">{moment.signal}</span>
        <span className="chip chip-plain landing-chip-action">{moment.action}</span>
      </p>
      <p>{moment.body}</p>
    </article>
  );
}

export function MomentsSection({ copy }: { copy: LandingCopy["moments"] }) {
  return (
    <section className="landing-moments" aria-labelledby={TITLE_ID}>
      <div className="wrap">
        <h2 id={TITLE_ID} className="section-title landing-title">
          {copy.title}
        </h2>
        <div className="landing-moments-pair">
          <Moment moment={copy.before} tone="tile-sage" />
          <Moment moment={copy.after} tone="tile-peach" />
        </div>
      </div>
    </section>
  );
}
