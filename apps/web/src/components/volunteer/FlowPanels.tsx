import type { EvidenceKind } from "../../lib/contracts";
import type { VolunteerCopy } from "../../lib/copy/volunteer";
import type { FailureReason } from "../../lib/volunteer/flow";
import { usePreviewUrl } from "./usePreviewUrl";

type CopyProps = { copy: VolunteerCopy };

export function SampleBadge({ copy }: CopyProps) {
  return <span className="chip chip-example">{copy.sampleChip}</span>;
}

type PreviewProps = CopyProps & {
  photo: Blob;
  sample: boolean;
  onSend: () => void;
  onRetake: () => void;
};

export function PhotoPreview({ copy, photo, sample, onSend, onRetake }: PreviewProps) {
  const url = usePreviewUrl(photo);
  return (
    <div className="flow-panel">
      {sample && <SampleBadge copy={copy} />}
      {url !== null && <img className="upload-photo" src={url} alt={copy.previewAlt} />}
      <p className="proto-note">{copy.previewNote}</p>
      <button type="button" className="btn btn-primary btn-lg btn-block" onClick={onSend}>
        {copy.sendPhoto}
      </button>
      <button type="button" className="btn btn-secondary btn-block" onClick={onRetake}>
        {copy.retake}
      </button>
    </div>
  );
}

type UploadingProps = CopyProps & { kind: EvidenceKind; progress: number; sample: boolean };

export function UploadingPanel({ copy, kind, progress, sample }: UploadingProps) {
  const percent = Math.round(progress * 100);
  const title = kind === "photo" ? copy.uploadingPhoto : copy.uploadingVoice;
  return (
    <div className="flow-panel" role="status">
      {sample && <SampleBadge copy={copy} />}
      <div className="proto-row proto-row--between">
        <strong>{title}</strong>
        <span className="num">{percent}%</span>
      </div>
      <div
        className="progress"
        role="progressbar"
        aria-valuenow={percent}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={copy.progressLabel}
      >
        <span style={{ width: `${percent}%` }} />
      </div>
      <p className="proto-note">{copy.keepOpen}</p>
    </div>
  );
}

export function ReadingPanel({ copy, sample }: CopyProps & { sample: boolean }) {
  return (
    <div className="flow-panel" role="status">
      {sample && <SampleBadge copy={copy} />}
      <span className="chip chip-gemini">{copy.geminiChip}</span>
      <strong>{copy.readingTitle}</strong>
      <p className="proto-note">{copy.readingNote}</p>
    </div>
  );
}

export function UnreadPanel({ copy, onDone }: CopyProps & { onDone: () => void }) {
  return (
    <div className="flow-panel" role="status">
      <p>{copy.readingSlow}</p>
      <button type="button" className="btn btn-secondary btn-block" onClick={onDone}>
        {copy.sendAnother}
      </button>
    </div>
  );
}

const FAILURE_TEXT: Record<FailureReason, (copy: VolunteerCopy) => string> = {
  prepare: (copy) => copy.prepareFailed,
  upload: (copy) => copy.uploadFailed,
  read: (copy) => copy.readFailed,
  mic: (copy) => copy.micDenied,
};

type FailureProps = CopyProps & {
  reason: FailureReason;
  onRetry: () => void;
  onReset: () => void;
};

export function FailurePanel({ copy, reason, onRetry, onReset }: FailureProps) {
  const canRetry = reason === "upload";
  return (
    <div className="flow-panel" role="alert">
      <p>{FAILURE_TEXT[reason](copy)}</p>
      {canRetry && (
        <button type="button" className="btn btn-primary btn-block" onClick={onRetry}>
          {copy.tryAgain}
        </button>
      )}
      <button type="button" className="btn btn-secondary btn-block" onClick={onReset}>
        {copy.back}
      </button>
    </div>
  );
}
