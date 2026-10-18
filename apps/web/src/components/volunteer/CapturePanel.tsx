import { useQuery } from "@tanstack/react-query";
import { type ChangeEvent, useRef } from "react";
import type { TaskType } from "../../lib/contracts";
import type { CopyLanguage } from "../../lib/copy/language";
import type { VolunteerCopy } from "../../lib/copy/volunteer";
import { kindsForTask, type PickKind, sentKindsFor } from "../../lib/volunteer/evidenceKinds";
import { EvidenceRow } from "./EvidenceRow";
import {
  FailurePanel,
  MicGatePanel,
  PhotoPreview,
  QueuedPanel,
  ReadingPanel,
  UnreadPanel,
  UploadingPanel,
} from "./FlowPanels";
import { inboxQuery } from "./inboxQuery";
import { useUploadFlow } from "./useUploadFlow";
import { VerdictCard } from "./VerdictCard";
import { VoiceRecording } from "./VoiceRecording";

type CapturePanelProps = {
  copy: VolunteerCopy;
  language: CopyLanguage;
  volunteerId: string;
  taskId: string;
  taskType: TaskType;
  locked: boolean;
};

export function CapturePanel({
  copy,
  language,
  volunteerId,
  taskId,
  taskType,
  locked,
}: CapturePanelProps) {
  const inbox = useQuery(inboxQuery(volunteerId));
  const flow = useUploadFlow({ volunteerId, taskId });
  const { state } = flow;
  const fileInput = useRef<HTMLInputElement>(null);
  const videoInput = useRef<HTMLInputElement>(null);

  function handleFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (file) void flow.choosePhoto(file, false);
  }

  function handleVideo(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (file) void flow.chooseVideo(file);
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
  if (state.step === "mic_gate") {
    return (
      <MicGatePanel
        copy={copy}
        allowed={state.allowed}
        onAllow={() => void flow.allowMicrophone()}
        onRecord={() => void flow.startRecording()}
        onBack={flow.reset}
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
  if (state.step === "queued") {
    return <QueuedPanel copy={copy} sample={state.sample} onDone={flow.reset} />;
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

  function handleAction(kind: PickKind) {
    if (kind === "photo") fileInput.current?.click();
    if (kind === "voice") void flow.askMicrophone();
    if (kind === "video") videoInput.current?.click();
  }

  return (
    <div className="flow-panel">
      <EvidenceRow
        copy={copy}
        kinds={kindsForTask(taskType)}
        sentKinds={sentKindsFor(inbox.data?.evidence ?? [], taskId)}
        busy={busy}
        onAction={handleAction}
        onSample={(item) => void flow.chooseSample(item)}
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
      <input
        ref={videoInput}
        className="visually-hidden"
        type="file"
        accept="video/mp4,video/quicktime,video/*"
        capture="environment"
        aria-label={copy.videoFile}
        tabIndex={-1}
        onChange={handleVideo}
      />
      <p className="proto-note">{copy.cameraHint}</p>
    </div>
  );
}
