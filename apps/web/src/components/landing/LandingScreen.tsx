import "./landing.css";
import { landingCopy } from "../../lib/copy/landing";
import { useCopyLanguage } from "../../lib/copy/language";
import { LanguageToggle } from "../LanguageToggle";
import { ClosingSection } from "./ClosingSection";
import { MomentsSection } from "./MomentsSection";
import { ProblemSection } from "./ProblemSection";
import { TourButtons } from "./TourButtons";
import { WhySection } from "./WhySection";

export function LandingScreen() {
  const copy = landingCopy(useCopyLanguage());
  return (
    <div className="landing">
      <section className="landing-hero">
        <div className="wrap">
          <div className="landing-hero-top">
            <LanguageToggle label={copy.toggleLabel} />
          </div>
          <h1 className="serif landing-h1">{copy.title}</h1>
          <TourButtons copy={copy} />
          <p className="muted landing-note">{copy.tourNote}</p>
        </div>
      </section>
      <ProblemSection copy={copy.problem} />
      <MomentsSection copy={copy.solution} />
      <WhySection copy={copy.why} />
      <ClosingSection copy={copy.closing} />
      <footer className="landing-team">
        <div className="wrap">
          <p className="muted">{copy.team}</p>
        </div>
      </footer>
    </div>
  );
}
