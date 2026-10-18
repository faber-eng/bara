import "./landing.css";
import { landingCopy } from "../../lib/copy/landing";
import { useCopyLanguage } from "../../lib/copy/language";
import { LanguageToggle } from "../LanguageToggle";
import { LoopSection } from "./LoopSection";
import { MomentsSection } from "./MomentsSection";
import { ProblemSection } from "./ProblemSection";
import { ProofSection } from "./ProofSection";
import { TourButtons } from "./TourButtons";
import { WhereSection } from "./WhereSection";

export function LandingScreen() {
  const language = useCopyLanguage();
  const copy = landingCopy(language);
  return (
    <div className="landing">
      <section className="landing-hero">
        <div className="wrap">
          <div className="landing-hero-top">
            <LanguageToggle label={copy.toggleLabel} />
          </div>
          <h1 className="serif landing-h1">{copy.title}</h1>
          <p className="lede">{copy.audience}</p>
          <TourButtons copy={copy} />
          <p className="muted landing-note">{copy.tourNote}</p>
        </div>
      </section>
      <ProblemSection copy={copy.problem} />
      <MomentsSection copy={copy.moments} />
      <LoopSection copy={copy.loop} />
      <ProofSection copy={copy.proof} language={language} />
      <WhereSection copy={copy.where} />
      <footer className="landing-team">
        <div className="wrap">
          <p className="muted">{copy.team}</p>
        </div>
      </footer>
    </div>
  );
}
