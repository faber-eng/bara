import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createMemoryHistory, RouterProvider } from "@tanstack/react-router";
import { render } from "@testing-library/react";
import { vi } from "vitest";
import { createAppRouter } from "./router";

export const healthBody = {
  status: "ok",
  models: { reasoning: "gemini-3.1-pro-preview", fast: "gemini-3.5-flash" },
  fallback_used: false,
  git_sha: "0123456789abcdef",
};

export type Handler = (init: RequestInit) => Response | Promise<Response>;
export type Handlers = Record<string, Handler>;

export function stubApi(handlers: Handlers) {
  const fetchMock = vi.fn().mockImplementation((path: string, init: RequestInit = {}) => {
    const key = `${init.method ?? "GET"} ${path}`;
    const handler = handlers[key];
    if (handler) return Promise.resolve(handler(init));
    if (path === "/api/health") return Promise.resolve(Response.json(healthBody));
    return Promise.resolve(new Response("not found", { status: 404 }));
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

export function callsTo(fetchMock: ReturnType<typeof vi.fn>, key: string) {
  return fetchMock.mock.calls.filter(([path, init]) => {
    const method = (init as RequestInit | undefined)?.method ?? "GET";
    return `${method} ${path}` === key;
  });
}

export function initOf(call: unknown[] | undefined): RequestInit {
  return (call?.[1] ?? {}) as RequestInit;
}

export function headerOf(call: unknown[] | undefined, name: string): string | null {
  const init = call?.[1] as RequestInit | undefined;
  return new Headers(init?.headers).get(name);
}

const NEVER_PENDING_MS = 2_000_000_000;

export function renderApp(path: string, queryClient = new QueryClient()) {
  const router = createAppRouter(createMemoryHistory({ initialEntries: [path] }));
  router.update({ defaultPendingMs: NEVER_PENDING_MS });
  const view = render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  return { ...view, router, queryClient };
}

class FakeDataLayer {
  static Polygon = class {};
  add() {}
  addListener() {
    return { remove: () => {} };
  }
  setMap() {}
}

export const outlineMapsApi = { Data: FakeDataLayer, LatLng: class {} };
