import type { Task } from "../../lib/contracts";
import type { CopyLanguage } from "../../lib/copy/language";
import type { VolunteerCopy } from "../../lib/copy/volunteer";
import { formatCoordinate } from "../../lib/geo";
import { formatDeadline, isPastDeadline } from "../../lib/volunteer/deadline";
import { CapturePanel } from "./CapturePanel";

type TaskCardProps = {
  copy: VolunteerCopy;
  language: CopyLanguage;
  volunteerId: string;
  task: Task;
  isArea: boolean;
  nowMs: number;
};

type TaskWords = { title: string; whatToSend: string };

function taskWords(task: Task, isArea: boolean, copy: VolunteerCopy): TaskWords {
  if (isArea && task.type === "dam_check") return copy.areaCheck;
  return { title: copy.taskTitles[task.type], whatToSend: copy.whatToSend[task.type] };
}

function mapUrl(task: Task): string {
  return `https://www.google.com/maps/search/?api=1&query=${task.target.lat},${task.target.lon}`;
}

export function TaskCard({ copy, language, volunteerId, task, isArea, nowMs }: TaskCardProps) {
  const words = taskWords(task, isArea, copy);
  const late = task.status !== "done" && isPastDeadline(task.deadline_at, nowMs);
  return (
    <article className="task-card" aria-label={words.title}>
      <div className="proto-row proto-row--between">
        <h2 className="task-title">{words.title}</h2>
        {late && <span className="chip chip-overdue">{copy.overdue}</span>}
      </div>
      <p className="task-row">
        <a href={mapUrl(task)} target="_blank" rel="noreferrer">
          {copy.openMap}
        </a>
        <span>
          {formatCoordinate(task.target.lat)}, {formatCoordinate(task.target.lon)}
        </span>
      </p>
      <p className="task-row">{copy.deadline(formatDeadline(task.deadline_at, language))}</p>
      <p className="task-row">{words.whatToSend}</p>
      {task.status === "done" && <span className="chip chip-resolved">{copy.doneChip}</span>}
      <CapturePanel
        copy={copy}
        language={language}
        volunteerId={volunteerId}
        taskId={task.id}
        taskType={task.type}
        locked={task.status === "done"}
      />
    </article>
  );
}
