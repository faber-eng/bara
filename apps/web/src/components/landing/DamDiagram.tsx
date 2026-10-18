import type { ReactNode } from "react";
import type { DamDiagramCopy } from "../../lib/copy/landing";

const VIEW_BOX = "0 22 320 168";
const SURFACE_Y = 60;
const PEAT_BOTTOM_Y = 180;
const CANAL_LEFT_X = 220;
const CANAL_RIGHT_X = 290;
const CANAL_BED_Y = 150;
const DAM_LEFT_X = 250;
const DAM_WIDTH = 12;
const LABEL_X = 14;

type DamPanelProps = { title: string; children: ReactNode };

function DamPanel({ title, children }: DamPanelProps) {
  return (
    <figure className="dam-panel">
      <svg viewBox={VIEW_BOX} role="img" aria-label={title} className="dam-svg">
        {children}
      </svg>
      <figcaption className="dam-caption">{title}</figcaption>
    </figure>
  );
}

function PeatAndCanal() {
  return (
    <>
      <rect
        className="dam-peat-wet"
        x={0}
        y={SURFACE_Y}
        width={320}
        height={PEAT_BOTTOM_Y - SURFACE_Y}
      />
      <rect
        className="dam-air"
        x={CANAL_LEFT_X}
        y={SURFACE_Y}
        width={CANAL_RIGHT_X - CANAL_LEFT_X}
        height={CANAL_BED_Y - SURFACE_Y}
      />
    </>
  );
}

function CanalWater({ upstreamY, downstreamY }: { upstreamY: number; downstreamY: number }) {
  const damRightX = DAM_LEFT_X + DAM_WIDTH;
  return (
    <>
      <rect
        className="dam-water"
        x={CANAL_LEFT_X}
        y={upstreamY}
        width={DAM_LEFT_X - CANAL_LEFT_X}
        height={CANAL_BED_Y - upstreamY}
      />
      <rect
        className="dam-water"
        x={damRightX}
        y={downstreamY}
        width={CANAL_RIGHT_X - damRightX}
        height={CANAL_BED_Y - downstreamY}
      />
    </>
  );
}

function WaterLine({ y, labelY, label }: { y: number; labelY: number; label: string }) {
  return (
    <>
      <line className="dam-line" x1={0} y1={y} x2={CANAL_LEFT_X} y2={y} />
      <text className="dam-label" x={120} y={labelY}>
        {label}
      </text>
    </>
  );
}

function CanalLabels({ copy, damTopY }: { copy: DamDiagramCopy; damTopY: number }) {
  return (
    <>
      <text
        className="dam-label"
        x={DAM_LEFT_X + DAM_WIDTH / 2}
        y={damTopY - 8}
        textAnchor="middle"
      >
        {copy.dam}
      </text>
      <text
        className="dam-label"
        x={(CANAL_LEFT_X + CANAL_RIGHT_X) / 2}
        y={168}
        textAnchor="middle"
      >
        {copy.canal}
      </text>
    </>
  );
}

const WORKING_WATER_Y = 72;
const WORKING_DAM_TOP_Y = 44;

function WorkingDam({ copy }: { copy: DamDiagramCopy }) {
  return (
    <DamPanel title={copy.works}>
      <PeatAndCanal />
      <CanalWater upstreamY={WORKING_WATER_Y} downstreamY={118} />
      <rect
        className="dam-wall"
        x={DAM_LEFT_X}
        y={WORKING_DAM_TOP_Y}
        width={DAM_WIDTH}
        height={CANAL_BED_Y - WORKING_DAM_TOP_Y}
      />
      <WaterLine y={WORKING_WATER_Y} labelY={WORKING_WATER_Y + 16} label={copy.waterLine} />
      <text className="dam-label" x={LABEL_X} y={130}>
        {copy.wetPeat}
      </text>
      <CanalLabels copy={copy} damTopY={WORKING_DAM_TOP_Y} />
    </DamPanel>
  );
}

const BROKEN_WATER_Y = 134;
const BROKEN_DAM_TOP_Y = 112;

function BrokenDam({ copy }: { copy: DamDiagramCopy }) {
  const damRightX = DAM_LEFT_X + DAM_WIDTH;
  const brokenTop = `${DAM_LEFT_X},${CANAL_BED_Y} ${DAM_LEFT_X},${BROKEN_DAM_TOP_Y + 6} ${DAM_LEFT_X + 4},${BROKEN_DAM_TOP_Y} ${DAM_LEFT_X + 8},${BROKEN_DAM_TOP_Y + 8} ${damRightX},${BROKEN_DAM_TOP_Y + 2} ${damRightX},${CANAL_BED_Y}`;
  return (
    <DamPanel title={copy.broken}>
      <PeatAndCanal />
      <rect
        className="dam-peat-dry"
        x={0}
        y={SURFACE_Y}
        width={CANAL_LEFT_X}
        height={BROKEN_WATER_Y - SURFACE_Y}
      />
      <CanalWater upstreamY={BROKEN_WATER_Y} downstreamY={BROKEN_WATER_Y} />
      <polygon className="dam-wall" points={brokenTop} />
      <WaterLine y={BROKEN_WATER_Y} labelY={BROKEN_WATER_Y + 16} label={copy.waterLine} />
      <text className="dam-label dam-label-strong" x={LABEL_X} y={84}>
        {copy.dryPeat}
      </text>
      <text className="dam-label" x={LABEL_X} y={116}>
        {copy.smoulder}
      </text>
      <circle className="dam-ember" cx={204} cy={112} r={4} />
      <circle className="dam-ember" cx={214} cy={116} r={3} />
      <text className="dam-label" x={LABEL_X} y={170}>
        {copy.wetPeat}
      </text>
      <CanalLabels copy={copy} damTopY={BROKEN_DAM_TOP_Y} />
    </DamPanel>
  );
}

export function DamDiagram({ copy }: { copy: DamDiagramCopy }) {
  return (
    <div className="dam-diagram">
      <WorkingDam copy={copy} />
      <BrokenDam copy={copy} />
      <p className="dam-note">{copy.radarNote}</p>
    </div>
  );
}
