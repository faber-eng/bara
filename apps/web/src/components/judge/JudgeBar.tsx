import { useSyncExternalStore } from "react";
import type { ClockState } from "../../lib/contracts";
import {
  getJudgeBarSnapshot,
  type JudgeBarState,
  setJudgeBar,
  subscribeJudgeBar,
} from "../../lib/judge/barState";
import { formatSimTimeShort } from "../../lib/simClock";
import { ClockControls } from "./ClockControls";
import { ClockReadout } from "./ClockReadout";
import { RoleSwitcher } from "./RoleSwitcher";
import { ScenarioControls } from "./ScenarioControls";

const PANEL_ID = "judge-panel";

function choose(state: JudgeBarState) {
  return () => setJudgeBar(state);
}

function JudgePill({ now }: { now: string }) {
  return (
    <button type="button" className="judge-pill" aria-expanded={false} onClick={choose("open")}>
      Demo Panel · {formatSimTimeShort(now)}
    </button>
  );
}

function JudgePanel({ now }: { now: string }) {
  return (
    <section id={PANEL_ID} className="judge-bar" aria-label="Demo Panel">
      <div className="judge-group">
        <RoleSwitcher />
      </div>
      <div className="judge-group">
        <ClockReadout now={now} />
        <ClockControls />
      </div>
      <div className="judge-group">
        <ScenarioControls />
      </div>
      <button
        type="button"
        className="judge-collapse"
        aria-expanded={true}
        aria-controls={PANEL_ID}
        onClick={choose("closed")}
      >
        <span className="visually-hidden">Collapse Demo Panel</span>
        <span aria-hidden="true">×</span>
      </button>
    </section>
  );
}

export function JudgeBar({ clock }: { clock: ClockState }) {
  const state = useSyncExternalStore(subscribeJudgeBar, getJudgeBarSnapshot);
  return (
    <div className="judge-dock">
      {state === "open" ? <JudgePanel now={clock.now} /> : <JudgePill now={clock.now} />}
    </div>
  );
}
