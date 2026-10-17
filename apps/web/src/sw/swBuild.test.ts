// @vitest-environment node
import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { renderServiceWorker, shellFiles } from "./swBuild";

const TEMPLATE = readFileSync(new URL("./sw.template.js", import.meta.url), "utf8");

describe("shellFiles", () => {
  it("lists the page, the manifest and every script and style the build emitted", () => {
    const shell = shellFiles(["assets/index-a1.js", "assets/index-b2.css", "sw.js", "logo.png"]);

    expect(shell).toEqual([
      "/",
      "/index.html",
      "/manifest.webmanifest",
      "/icon.svg",
      "/assets/index-a1.js",
      "/assets/index-b2.css",
    ]);
  });
});

describe("renderServiceWorker", () => {
  it("fills the file list and a version that changes with the list", () => {
    const first = renderServiceWorker(TEMPLATE, ["/", "/assets/a.js"]);
    const second = renderServiceWorker(TEMPLATE, ["/", "/assets/b.js"]);

    expect(first).toContain('["/","/assets/a.js"]');
    expect(first).not.toContain("__SHELL__");
    expect(first).not.toContain("__VERSION__");
    expect(first.match(/bara-shell-\w+/)?.[0]).not.toBe(second.match(/bara-shell-\w+/)?.[0]);
  });

  it("never touches the API", () => {
    expect(TEMPLATE).toContain('url.pathname.startsWith("/api/")');
  });
});
