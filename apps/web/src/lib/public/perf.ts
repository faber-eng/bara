const marked = new Set<string>();

export function markOnce(name: string): void {
  if (marked.has(name)) return;
  marked.add(name);
  try {
    performance.mark(name);
  } catch {
    return;
  }
}

export function resetMarks(): void {
  marked.clear();
}
