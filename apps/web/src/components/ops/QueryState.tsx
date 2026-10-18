import type { UseQueryResult } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { ApiError } from "../../lib/api/client";
import { InlineLoading } from "../LoadingPanel";

const FORBIDDEN_STATUSES = [401, 403];

const OPS_FORBIDDEN_TEXT = "This account does not have the ops role.";

function failureMessage(error: Error, label: string, forbiddenText: string): string {
  if (error instanceof ApiError && FORBIDDEN_STATUSES.includes(error.status)) {
    return forbiddenText;
  }
  return `Could not load ${label}.`;
}

type QueryStateProps<T> = {
  query: UseQueryResult<T, Error>;
  label: string;
  emptyText: string;
  empty?: ReactNode;
  forbiddenText?: string;
  isEmpty: (data: T) => boolean;
  children: (data: T) => ReactNode;
};

export function QueryState<T>({
  query,
  label,
  emptyText,
  empty,
  forbiddenText = OPS_FORBIDDEN_TEXT,
  isEmpty,
  children,
}: QueryStateProps<T>) {
  if (query.isPending) {
    return <InlineLoading text={`Loading ${label}`} />;
  }
  if (query.isError) {
    return (
      <div role="alert" className="ops-state">
        <p>{failureMessage(query.error, label, forbiddenText)}</p>
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
  if (isEmpty(query.data)) return empty ?? <p className="ops-state">{emptyText}</p>;
  return <>{children(query.data)}</>;
}
