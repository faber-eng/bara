export function assigneeName(names: Record<string, string>, assigneeId: string): string {
  const name = names[assigneeId];
  if (name === undefined || name === "") return assigneeId;
  return name;
}
