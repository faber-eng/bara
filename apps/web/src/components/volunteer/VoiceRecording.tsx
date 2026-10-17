import { useEffect, useState } from "react";
import type { VolunteerCopy } from "../../lib/copy/volunteer";

const TICK_MS = 1_000;

function clock(seconds: number): string {
  const minutes = Math.floor(seconds / 60);
  return `${minutes}:${String(seconds % 60).padStart(2, "0")}`;
}

type VoiceRecordingProps = { copy: VolunteerCopy; onStop: () => void };

export function VoiceRecording({ copy, onStop }: VoiceRecordingProps) {
  const [seconds, setSeconds] = useState(0);

  useEffect(() => {
    const timer = setInterval(() => setSeconds((previous) => previous + 1), TICK_MS);
    return () => clearInterval(timer);
  }, []);

  return (
    <div className="flow-panel">
      <div className="timer" role="timer" aria-live="off">
        {clock(seconds)}
      </div>
      <p className="proto-note">
        {copy.recording}. {copy.recordingHint}
      </p>
      <button type="button" className="btn btn-danger btn-lg btn-block" onClick={onStop}>
        {copy.stopRecording}
      </button>
    </div>
  );
}
