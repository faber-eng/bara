import type { AgentRun, ToolCall } from "../../lib/contracts";
import { toolCallArgs } from "../../lib/ops/caseDrawer";
import { formatSimTime } from "../../lib/simClock";

function ToolCallRow({ call }: { call: ToolCall }) {
  return (
    <li>
      <span aria-hidden="true" className="run-icon">
        ✓
      </span>
      <div>
        <code>{call.name}</code>
        <span className="run-sum">{toolCallArgs(call.args)}</span>
        <span className="run-sum">{call.result_summary}</span>
      </div>
      <span className="run-ms">{call.ms} ms</span>
    </li>
  );
}

type RunProps = { run: AgentRun; open: boolean; onToggle: (open: boolean) => void };

function Run({ run, open, onToggle }: RunProps) {
  return (
    <details open={open} onToggle={(event) => onToggle(event.currentTarget.open)}>
      <summary>
        <span className="chip chip-gemini">Gemini</span> {run.trigger} ·{" "}
        {formatSimTime(run.started_at)}
      </summary>
      <p className="ops-meta">
        Model {run.model} · prompt {run.prompt_version} · {run.ms} ms
      </p>
      <ol className="run">
        {run.tool_calls.map((call) => (
          <ToolCallRow key={`${call.name}-${call.ms}-${call.result_summary}`} call={call} />
        ))}
      </ol>
      {run.final_json !== null && (
        <p className="run-decision">
          <strong>{run.final_json.decision}</strong>: {run.final_json.reason}
        </p>
      )}
    </details>
  );
}

type AgentRunsProps = {
  runs: AgentRun[];
  openRunId: string | null;
  onOpenChange: (runId: string, open: boolean) => void;
};

export function AgentRuns({ runs, openRunId, onOpenChange }: AgentRunsProps) {
  if (runs.length === 0) return <p className="ops-meta">The agent has not run on this case.</p>;
  return (
    <div className="agent-runs">
      {runs.map((run) => (
        <Run
          key={run.id}
          run={run}
          open={run.id === openRunId}
          onToggle={(open) => onOpenChange(run.id, open)}
        />
      ))}
    </div>
  );
}
