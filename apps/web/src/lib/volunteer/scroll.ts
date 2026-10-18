const NEAR_BOTTOM_PX = 48;

export type ScrollMetrics = { scrollHeight: number; scrollTop: number; clientHeight: number };

export type ScrollDecision = "follow" | "notify";

export function isNearBottom(metrics: ScrollMetrics): boolean {
  const gap = metrics.scrollHeight - metrics.scrollTop - metrics.clientHeight;
  return gap <= NEAR_BOTTOM_PX;
}

export function scrollDecision(input: { pinned: boolean; newestIsMine: boolean }): ScrollDecision {
  if (input.pinned || input.newestIsMine) return "follow";
  return "notify";
}
