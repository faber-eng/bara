import type { ClockState } from "../../lib/contracts";
import { ClockControls } from "./ClockControls";
import { ClockReadout } from "./ClockReadout";
import { RoleSwitcher } from "./RoleSwitcher";
import { ScenarioControls } from "./ScenarioControls";

export function JudgeBar({ clock }: { clock: ClockState }) {
  return (
    <div className="judge-wrap">
      <section className="judge-bar" aria-label="Judge mode">
        <strong>Judge mode</strong>
        <span className="judge-sep" />
        <RoleSwitcher />
        <ClockReadout now={clock.now} />
        <ClockControls />
        <ScenarioControls />
      </section>
    </div>
  );
}
