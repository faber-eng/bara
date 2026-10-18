import { type ReactNode, useState } from "react";
import type { DamState } from "../../lib/contracts";
import type { DetailCopy, MapKeyScreen } from "../../lib/copy/detail";
import { DAM_STATES, damColor } from "../../lib/ops/cellLayer";
import { definitionFor } from "../../lib/ops/mapLayers";

export type MapKeyMark =
  | "cell"
  | "dam"
  | "case"
  | "areaShape"
  | "areaCell"
  | "burnScar"
  | "reignition"
  | "peat";

const RAMP_STEPS = [1, 2, 3, 4, 5] as const;
const WIDE_SCREEN = "(min-width: 601px)";

type DamKeyRow = { state: DamState; color: string };

export function damKeyRows(): DamKeyRow[] {
  const rows: DamKeyRow[] = [];
  const seen = new Set<string>();
  for (const state of DAM_STATES) {
    const color = damColor(state);
    if (seen.has(color)) continue;
    seen.add(color);
    rows.push({ state, color });
  }
  return rows;
}

function startsOpen(): boolean {
  if (typeof window.matchMedia !== "function") return true;
  return window.matchMedia(WIDE_SCREEN).matches;
}

function Ramp({ round = false }: { round?: boolean }) {
  return (
    <span className={round ? "mv-ramp mv-ramp-round" : "mv-ramp"} aria-hidden="true">
      {RAMP_STEPS.map((step) => (
        <span key={step} style={{ background: `var(--risk-${step})` }} />
      ))}
    </span>
  );
}

function Swatches({ colors }: { colors: readonly string[] }) {
  return (
    <span className="mv-swatches" aria-hidden="true">
      {colors.map((color) => (
        <span key={color} className="mv-swatch-square" style={{ background: color }} />
      ))}
    </span>
  );
}

function legendColors(kind: "burn_scars" | "peat"): string[] {
  const legend = definitionFor(kind).legend;
  if (legend.kind !== "swatches") return [];
  return legend.items.map((item) => item.color);
}

function KeyRow({ swatch, children }: { swatch: ReactNode; children: ReactNode }) {
  return (
    <li className="mv-key-row">
      {swatch}
      <span>{children}</span>
    </li>
  );
}

function DamRows({ copy }: { copy: DetailCopy }) {
  return (
    <li className="mv-key-row mv-key-dams">
      <span className="mv-swatch-dot mv-swatch-dot-plain" aria-hidden="true" />
      <span>
        {copy.key.dam}
        <ul className="mv-key-states">
          {damKeyRows().map((row) => (
            <li key={row.state}>
              <span
                className="mv-swatch-dot"
                style={{ background: row.color }}
                aria-hidden="true"
              />
              <span>{copy.damStates[row.state]}</span>
            </li>
          ))}
        </ul>
      </span>
    </li>
  );
}

function CellRow({ copy }: { copy: DetailCopy }) {
  return (
    <li className="mv-key-row mv-key-cells">
      <span className="mv-key-scale">
        <Ramp />
        <span className="mv-key-ends num" aria-hidden="true">
          <span>{copy.key.scaleLow}</span>
          <span>{copy.key.scaleHigh}</span>
        </span>
      </span>
      <span>{copy.key.cell}</span>
    </li>
  );
}

function MarkRow({ mark, copy }: { mark: MapKeyMark; copy: DetailCopy }) {
  switch (mark) {
    case "cell":
      return <CellRow copy={copy} />;
    case "dam":
      return <DamRows copy={copy} />;
    case "case":
      return (
        <KeyRow swatch={<span className="mv-swatch-outline" aria-hidden="true" />}>
          {copy.key.case}
        </KeyRow>
      );
    case "areaShape":
      return (
        <KeyRow swatch={<span className="mv-swatch-shape" aria-hidden="true" />}>
          {copy.key.areaShape}
        </KeyRow>
      );
    case "areaCell":
      return <KeyRow swatch={<Ramp round />}>{copy.key.areaCell}</KeyRow>;
    case "burnScar":
      return (
        <KeyRow swatch={<Swatches colors={legendColors("burn_scars")} />}>
          {copy.key.burnScar}
        </KeyRow>
      );
    case "reignition":
      return <KeyRow swatch={<Ramp />}>{copy.key.reignition}</KeyRow>;
    case "peat":
      return <KeyRow swatch={<Swatches colors={legendColors("peat")} />}>{copy.key.peat}</KeyRow>;
    default:
      return unhandledMark(mark);
  }
}

function unhandledMark(mark: never): never {
  throw new Error(`unhandled map key mark: ${String(mark)}`);
}

type MapKeyProps = {
  marks: readonly MapKeyMark[];
  copy: DetailCopy;
  screen: MapKeyScreen;
  children?: ReactNode;
};

export function MapKey({ marks, copy, screen, children }: MapKeyProps) {
  const [open] = useState(startsOpen);
  return (
    <section className="mv-key" aria-label={copy.key.title}>
      <details className="mv-key-fold" open={open}>
        <summary className="mv-key-title">{copy.key.title}</summary>
        <ul className="mv-key-rows">
          {marks.map((mark) => (
            <MarkRow key={mark} mark={mark} copy={copy} />
          ))}
        </ul>
        {children}
        <details className="mv-key-explain">
          <summary>{copy.key.explainToggle}</summary>
          <p>{copy.key.explain[screen]}</p>
        </details>
      </details>
    </section>
  );
}
