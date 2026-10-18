import { countdown, countdownLabel } from "../../lib/simClock";

type CountdownProps = { deadline: string; nowMs: number; simClock: boolean };

export function countdownText({ deadline, nowMs, simClock }: CountdownProps): string {
  const suffix = simClock ? " (sim clock)" : "";
  return `${countdownLabel(countdown(deadline, nowMs))}${suffix}`;
}

export function Countdown({ deadline, nowMs, simClock }: CountdownProps) {
  const late = countdown(deadline, nowMs).kind === "overdue";
  const className = late ? "countdown countdown-late" : "countdown";
  return <span className={className}>{countdownText({ deadline, nowMs, simClock })}</span>;
}
