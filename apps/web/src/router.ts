import { createRouter, type RouterHistory } from "@tanstack/react-router";
import { LoadingPanel } from "./components/LoadingPanel";
import { routeTree } from "./routeTree.gen";

const PENDING_DELAY_MS = 150;

export function createAppRouter(history?: RouterHistory) {
  return createRouter({
    routeTree,
    history,
    defaultPendingComponent: LoadingPanel,
    defaultPendingMs: PENDING_DELAY_MS,
  });
}

declare module "@tanstack/react-router" {
  interface Register {
    router: ReturnType<typeof createAppRouter>;
  }
}
