export function tileUrl(template: string, x: number, y: number, zoom: number): string | null {
  const worldSize = 2 ** zoom;
  if (y < 0 || y >= worldSize) return null;
  const wrappedX = ((x % worldSize) + worldSize) % worldSize;
  return template
    .replace("{z}", String(zoom))
    .replace("{x}", String(wrappedX))
    .replace("{y}", String(y));
}
