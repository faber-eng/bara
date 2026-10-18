import type { PickKind } from "../../lib/volunteer/evidenceKinds";

const PATHS = {
  photo: (
    <>
      <path d="M4 8h3l1.5-2h7L17 8h3v11H4z" />
      <circle cx="12" cy="13" r="3.5" />
    </>
  ),
  voice: (
    <>
      <rect x="9" y="3" width="6" height="11" rx="3" />
      <path d="M5.5 11.5a6.5 6.5 0 0 0 13 0M12 18v3" />
    </>
  ),
  video: (
    <>
      <rect x="3" y="6" width="12" height="12" rx="2" />
      <path d="m15 10.5 6-3v9l-6-3z" />
    </>
  ),
} as const satisfies Record<PickKind, React.ReactNode>;

const STROKE = {
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.8,
  strokeLinecap: "round",
  strokeLinejoin: "round",
} as const;

export function KindIcon({ kind }: { kind: PickKind }) {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false" {...STROKE}>
      {PATHS[kind]}
    </svg>
  );
}

export function CheckIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false" {...STROKE}>
      <path d="m5 12.5 4.5 4.5L19 7.5" />
    </svg>
  );
}
