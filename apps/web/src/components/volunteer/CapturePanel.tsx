import { type ChangeEvent, useRef } from "react";
import type { CopyLanguage } from "../../lib/copy/language";
import type { VolunteerCopy } from "../../lib/copy/volunteer";
import { SamplePicker } from "../samples/SamplePicker";
import {
  FailurePanel,
  PhotoPreview,
  ReadingPanel,
  StoredPanel,
  UnreadPanel,
  UploadingPanel,
} from "./FlowPanels";
import { useUploadFlow } from "./useUploadFlow";
import { VerdictCard } from "./VerdictCard";
import { VoiceRecording } from "./VoiceRecording";

type CapturePanelProps = {
  copy: VolunteerCopy;
  language: CopyLanguage;
  volunteerId: string;
  taskId: string;
  locked: boolean;
};

export function CapturePanel({ copy, language, volunteerId, taskId, locked }: CapturePanelProps) {
  const flow = useUploadFlow({ volunteerId, taskId });
  const { state } = flow;
  const fileInput = useRef<HTMLInputElement>(null);

  function handleFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (file) void flow.choosePhoto(file, false);
  }

  if (state.step === "preview") {
    return (
      <PhotoPreview
        copy={copy}
        photo={state.photo}
        sample={state.sample}
        onSend={() => void flow.sendPhoto()}
        onRetake={flow.reset}
      />
    );
  }
  if (state.step === "recording") {
    return <VoiceRecording copy={copy} onStop={() => void flow.stopRecording()} />;
  }
  if (state.step === "uploading") {
    return (
      <UploadingPanel
        copy={copy}
        kind={state.kind}
        progress={state.progress}
        sample={state.sample}
      />
    );
  }
  if (state.step === "reading") return <ReadingPanel copy={copy} sample={state.sample} />;
  if (state.step === "done") {
    return (
      <VerdictCard copy={copy} language={language} evidence={state.evidence} onDone={flow.reset} />
    );
  }
  if (state.step === "stored") {
    return <StoredPanel copy={copy} sample={state.sample} onDone={flow.reset} />;
  }
  if (state.step === "unread") return <UnreadPanel copy={copy} onDone={flow.reset} />;
  if (state.step === "failed") {
    return (
      <FailurePanel
        copy={copy}
        reason={state.reason}
        onRetry={() => void flow.retry()}
        onReset={flow.reset}
      />
    );
  }

  if (locked) return null;
  const busy = state.step === "preparing";

  return (
    <div className="flow-panel">
      <div className="capture">
        <button
          type="button"
          className="btn btn-primary btn-lg"
          disabled={busy}
          onClick={() => fileInput.current?.click()}
        >
          {copy.takePhoto}
        </button>
        <SamplePicker
          kind="photo"
          copy={copy}
          disabled={busy}
          onPick={(item) => void flow.chooseSample(item)}
        />
        <input
          ref={fileInput}
          className="visually-hidden"
          type="file"
          accept="image/*"
          capture="environment"
          aria-label={copy.photoFile}
          tabIndex={-1}
          onChange={handleFile}
        />
        <button
          type="button"
          className="btn btn-primary btn-lg"
          disabled={busy}
          onClick={() => void flow.startRecording()}
        >
          {copy.recordVoice}
        </button>
        <SamplePicker
          kind="voice"
          copy={copy}
          disabled={busy}
          onPick={(item) => void flow.chooseSample(item)}
        />
      </div>
      <p className="proto-note">{copy.cameraHint}</p>
    </div>
  );
}
