import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createMemoryHistory, RouterProvider } from "@tanstack/react-router";
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { LoadingPanel } from "./components/LoadingPanel";
import { createAppRouter } from "./router";

const validBody = {
  status: "ok",
  models: { reasoning: "gemini-3.1-pro-preview", fast: "gemini-3.5-flash" },
  fallback_used: false,
  git_sha: "0123456789abcdef",
};

function renderAt(path: string) {
  const router = createAppRouter(createMemoryHistory({ initialEntries: [path] }));
  const queryClient = new QueryClient();
  render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}

describe("app routes", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation(() => Promise.resolve(Response.json(validBody))),
    );
    return () => vi.unstubAllGlobals();
  });

  it.each([["/", "Landing and tour"]])(
    "renders %s with its title and the health footer",
    async (path, title) => {
      renderAt(path);

      expect(await screen.findByRole("heading", { level: 1, name: title })).toBeInTheDocument();
      expect(screen.getByText(path, { selector: ".spec-code" })).toBeInTheDocument();
      expect(await screen.findByText("API ok")).toBeInTheDocument();
    },
  );

  it("opens the volunteer screen for the id in the URL", async () => {
    renderAt("/v/demo");

    expect(
      await screen.findByRole("heading", { level: 1, name: "Tugas Anda" }),
    ).toBeInTheDocument();
    expect(await screen.findByRole("article", { name: "Cek sekat kanal" })).toBeInTheDocument();
  });

  it("opens the draw an area screen", async () => {
    renderAt("/area/new");

    expect(
      await screen.findByRole("heading", { level: 1, name: "Gambar area" }),
    ).toBeInTheDocument();
  });

  it("marks the active screen in the app bar", async () => {
    renderAt("/ops");

    expect(await screen.findByRole("link", { name: "Ops" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(screen.getByRole("link", { name: "Public" })).not.toHaveAttribute("aria-current");
  });

  it("still renders the route when the health call fails", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("network down")));
    renderAt("/");

    expect(
      await screen.findByRole("heading", { level: 1, name: "Landing and tour" }),
    ).toBeInTheDocument();
    expect(await screen.findByText("API unreachable", {}, { timeout: 3000 })).toBeInTheDocument();
  });

  it("renders a not-found screen for an unknown path", async () => {
    renderAt("/nope");

    expect(
      await screen.findByRole("heading", { level: 1, name: "This page does not exist." }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Go to the start" })).toHaveAttribute("href", "/");
  });
});

describe("router pending UI", () => {
  it("uses the shared loading panel after a short delay", () => {
    const router = createAppRouter();

    expect(router.options.defaultPendingComponent).toBe(LoadingPanel);
    expect(router.options.defaultPendingMs).toBeLessThan(500);
  });
});
