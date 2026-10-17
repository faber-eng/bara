import { useEffect, useState } from "react";
import { type AuthUser, subscribeAuthUser } from "./auth";

export type AuthState =
  | { status: "loading" }
  | { status: "failed" }
  | { status: "ready"; user: AuthUser | null };

export function useAuthUser(): AuthState {
  const [state, setState] = useState<AuthState>({ status: "loading" });

  useEffect(
    () =>
      subscribeAuthUser(
        (user) => setState({ status: "ready", user }),
        () => setState({ status: "failed" }),
      ),
    [],
  );

  return state;
}
