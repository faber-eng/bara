export type OpsTab = "ranked" | "cases";

export function parseOpsTab(value: unknown): OpsTab | undefined {
  if (value === "ranked" || value === "cases") return value;
  return undefined;
}
