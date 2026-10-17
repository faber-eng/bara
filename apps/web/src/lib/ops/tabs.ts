export type OpsTab = "ranked" | "cases" | "review";

export function parseOpsTab(value: unknown): OpsTab | undefined {
  if (value === "ranked" || value === "cases" || value === "review") return value;
  return undefined;
}
