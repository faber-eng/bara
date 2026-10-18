import { useState } from "react";
import type { EvidenceKind, SampleItem, SampleKind } from "../../lib/contracts";
import type { VolunteerCopy } from "../../lib/copy/volunteer";
import { evidenceKindOf, type PickKind } from "../../lib/volunteer/evidenceKinds";
import { Dialog } from "../Dialog";
import { SamplePicker } from "../samples/SamplePicker";
import { CheckIcon, KindIcon } from "./EvidenceIcons";

type EvidenceRowProps = {
  copy: VolunteerCopy;
  kinds: readonly PickKind[];
  sentKinds: ReadonlySet<EvidenceKind>;
  busy: boolean;
  onAction: (kind: PickKind) => void;
  onSample: (item: SampleItem) => void;
};

const SAMPLE_KIND_OF: Partial<Record<PickKind, SampleKind>> = {
  photo: "photo",
  voice: "voice",
};

function actionLabel(kind: PickKind, copy: VolunteerCopy): string {
  if (kind === "photo") return copy.takePhoto;
  if (kind === "voice") return copy.recordVoice;
  return copy.recordVideo;
}

type KindDialogProps = {
  copy: VolunteerCopy;
  kind: PickKind;
  busy: boolean;
  onAction: (kind: PickKind) => void;
  onSample: (item: SampleItem) => void;
  onClose: () => void;
};

function KindDialog({ copy, kind, busy, onAction, onSample, onClose }: KindDialogProps) {
  const sampleKind = SAMPLE_KIND_OF[kind];

  function handleAction() {
    onClose();
    onAction(kind);
  }

  function handleSample(item: SampleItem) {
    onClose();
    onSample(item);
  }

  return (
    <Dialog title={copy.addDialogTitle[kind]} onClose={onClose}>
      <div className="dialog-choices">
        <button
          type="button"
          className="btn btn-primary btn-lg"
          disabled={busy}
          onClick={handleAction}
        >
          {actionLabel(kind, copy)}
        </button>
        {sampleKind && (
          <SamplePicker kind={sampleKind} copy={copy} disabled={busy} onPick={handleSample} />
        )}
        <button type="button" className="btn btn-secondary btn-sm" onClick={onClose}>
          {copy.cancel}
        </button>
      </div>
    </Dialog>
  );
}

export function EvidenceRow({
  copy,
  kinds,
  sentKinds,
  busy,
  onAction,
  onSample,
}: EvidenceRowProps) {
  const [openKind, setOpenKind] = useState<PickKind | null>(null);

  return (
    <>
      <fieldset className="evidence-row">
        <legend className="visually-hidden">{copy.evidenceRowLabel}</legend>
        {kinds.map((kind) => {
          const sent = sentKinds.has(evidenceKindOf(kind));
          return (
            <button
              key={kind}
              type="button"
              className={sent ? "evidence-btn evidence-btn--done" : "evidence-btn"}
              disabled={busy}
              aria-haspopup="dialog"
              aria-label={sent ? copy.kindSent(copy.kindLabels[kind]) : copy.kindLabels[kind]}
              onClick={() => setOpenKind(kind)}
            >
              {sent ? <CheckIcon /> : <KindIcon kind={kind} />}
              <span aria-hidden="true">{copy.kindLabels[kind]}</span>
            </button>
          );
        })}
      </fieldset>
      {openKind && (
        <KindDialog
          copy={copy}
          kind={openKind}
          busy={busy}
          onAction={onAction}
          onSample={onSample}
          onClose={() => setOpenKind(null)}
        />
      )}
    </>
  );
}
