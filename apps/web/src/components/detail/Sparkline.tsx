const WIDTH = 120;
const HEIGHT = 28;
const PAD = 2;

function points(values: readonly number[]): string {
  const low = Math.min(...values);
  const span = Math.max(...values) - low || 1;
  const step = (WIDTH - PAD * 2) / Math.max(1, values.length - 1);
  return values
    .map((value, index) => {
      const x = PAD + index * step;
      const y = HEIGHT - PAD - ((value - low) / span) * (HEIGHT - PAD * 2);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
}

export function Sparkline({ values }: { values: readonly number[] }) {
  return (
    <svg
      className="mv-spark"
      width={WIDTH}
      height={HEIGHT}
      viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
      aria-hidden="true"
    >
      <polyline points={points(values)} fill="none" stroke="currentColor" strokeWidth="2" />
    </svg>
  );
}
