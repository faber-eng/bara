import { useQuery } from "@tanstack/react-query";
import { fetchHealth, type Health } from "../lib/health";

const SHORT_SHA_LENGTH = 7;

function shortSha(sha: string): string {
  return sha.slice(0, SHORT_SHA_LENGTH);
}

function HealthOk({ health }: { health: Health }) {
  return (
    <>
      <span className="chip">API {health.status}</span>
      <span className="shell-foot-facts">
        <span>
          reasoning <span className="spec-code">{health.models.reasoning}</span>
        </span>
        <span>
          fast <span className="spec-code">{health.models.fast}</span>
        </span>
        <span>
          sha <span className="spec-code">{shortSha(health.git_sha)}</span>
        </span>
      </span>
      {health.fallback_used && <span className="chip chip-human-review">fallback in use</span>}
    </>
  );
}

function HealthDown({ onRetry, isRetrying }: { onRetry: () => void; isRetrying: boolean }) {
  return (
    <>
      <span className="chip chip-escalated">API unreachable</span>
      <span>GET /api/health did not answer.</span>
      <button
        type="button"
        className="btn btn-white btn-sm"
        onClick={onRetry}
        disabled={isRetrying}
      >
        Check again
      </button>
    </>
  );
}

function HealthStatus() {
  const health = useQuery({
    queryKey: ["health"],
    queryFn: ({ signal }) => fetchHealth(signal),
    staleTime: 60_000,
    retry: 1,
  });

  if (health.isPending) return <span className="chip">Checking API</span>;
  if (health.isError) {
    return <HealthDown onRetry={() => void health.refetch()} isRetrying={health.isFetching} />;
  }
  return <HealthOk health={health.data} />;
}

export function HealthFooter() {
  return (
    <footer className="shell-foot on-dark" aria-live="polite">
      <HealthStatus />
    </footer>
  );
}
