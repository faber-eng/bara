export const RISK_COLORS = ["#fceace", "#f6cf9f", "#e9a066", "#c4612a", "#8a3a12"] as const;

const SCORE_STEP = 20;

export function scoreColor(score: number): string {
  const step = Math.floor(score / SCORE_STEP);
  const level = Math.min(RISK_COLORS.length - 1, Math.max(0, step));
  return RISK_COLORS[level] ?? RISK_COLORS[0];
}
