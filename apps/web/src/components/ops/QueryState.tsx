import type { UseQueryResult } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { ApiError } from "../../lib/api/client";

const FORBIDDEN_STATUSES = [401, 403];

function failureMessage(error: Error, label: string): string {
  if (error instanceof ApiError && FORBIDDEN_STATUSES.includes(error.status)) {
    return "This account does not have the ops role.";
  }
  return `Could not load ${label}.`;
}

type QueryStateProps<T> = {
  query: UseQueryResult<T, Error>;
  label: string;
  emptyText: string;
  isEmpty: (data: T) => boolean;
  children: (data: T) => ReactNode;
};

export function QueryState<T>({ query, label, emptyText, isEmpty, children }: QueryStateProps<T>) {
  if (query.isPending) {
    return (
      <p role="status" className="ops-state">
        Loading {label}
      </p>
    );
  }
  if (query.isError) {
    return (
      <div role="alert" className="ops-state">
        <p>{failureMessage(query.error, label)}</p>
        <button
          type="button"
          className="btn btn-secondary btn-sm"
          onClick={() => void query.refetch()}
        >
          Try again
        </button>
      </div>
    );
  }
  if (isEmpty(query.data)) return <p className="ops-state">{emptyText}</p>;
  return <>{children(query.data)}</>;
}
