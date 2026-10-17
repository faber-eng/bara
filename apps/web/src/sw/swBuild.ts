import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import type { Plugin } from "vite";

const TEMPLATE = fileURLToPath(new URL("./sw.template.js", import.meta.url));
const STATIC_SHELL = ["/", "/index.html", "/manifest.webmanifest", "/icon.svg"];
const SHELL_EXTENSIONS = [".js", ".css"];

export function shellFiles(emitted: string[]): string[] {
  const assets = emitted
    .filter((name) => name !== "sw.js")
    .filter((name) => SHELL_EXTENSIONS.some((extension) => name.endsWith(extension)))
    .map((name) => `/${name}`);
  return [...STATIC_SHELL, ...assets.sort()];
}

export function renderServiceWorker(template: string, shell: string[]): string {
  const version = createHash("sha256").update(shell.join("\n")).digest("hex").slice(0, 12);
  return template.replace("__VERSION__", version).replace("__SHELL__", JSON.stringify(shell));
}

export function serviceWorkerPlugin(): Plugin {
  return {
    name: "bara-service-worker",
    apply: "build",
    generateBundle(_options, bundle) {
      const shell = shellFiles(Object.keys(bundle));
      const source = renderServiceWorker(readFileSync(TEMPLATE, "utf8"), shell);
      this.emitFile({ type: "asset", fileName: "sw.js", source });
    },
  };
}
