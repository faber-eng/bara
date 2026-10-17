import { countdown, countdownLabel } from "../../lib/simClock";

type CountdownProps = { deadline: string; nowMs: number; simClock: boolean };

export function Countdown({ deadline, nowMs, simClock }: CountdownProps) {
  const value = countdown(deadline, nowMs);
  const className = value.kind === "overdue" ? "countdown countdown-late" : "countdown";
  const suffix = simClock ? " (sim clock)" : "";
  return <span className={className}>{`${countdownLabel(value)}${suffix}`}</span>;
}
