import { defineConfig } from "vite";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const factualCandidatePath = resolve(import.meta.dirname, "../data/review/factual-snapshot-candidate.json");
const phase4bCandidatePath = resolve(import.meta.dirname, "../state/review/phase4b-read-model-candidate.json");
const motionQaFixturePath = resolve(import.meta.dirname, "fixtures/motion-qa-read-model.json");

function localPhase4bCheckpoint() {
  return {
    name: "auxsays-local-phase4b-checkpoint",
    apply: "serve",
    configureServer(server) {
      const host = server.config.server.host;
      const loopbackOnly = host === "127.0.0.1" || host === "localhost" || host === "::1";
      server.middlewares.use((request, response, next) => {
        const pathname = (request.url ?? "").split("?", 1)[0];
        if (pathname.endsWith("/__local-review/motion-qa")) {
          if (!loopbackOnly) {
            response.statusCode = 403;
            response.end("Motion QA requires a loopback-only development server.");
            return;
          }
          const factual = JSON.stringify(JSON.parse(readFileSync(factualCandidatePath, "utf8"))).replaceAll("<", "\\u003c");
          const motion = JSON.stringify(JSON.parse(readFileSync(motionQaFixturePath, "utf8"))).replaceAll("<", "\\u003c");
          response.statusCode = 200;
          response.setHeader("Content-Type", "text/html; charset=utf-8");
          response.setHeader("Cache-Control", "no-store");
          response.end(`<!doctype html><meta charset="utf-8"><title>Loading Motion QA</title><script>localStorage.removeItem("auxsays.localPhase4bState");localStorage.setItem("auxsays.localFactualCandidate",${JSON.stringify(factual)});localStorage.setItem("auxsays.localMotionQaState",${JSON.stringify(motion)});location.replace("/systems-monitor/?view=summary");</script>`);
          return;
        }
        if (!pathname.endsWith("/__local-review/phase4b")) return next();
        if (!loopbackOnly) {
          response.statusCode = 403;
          response.end("Local review loader requires a loopback-only development server.");
          return;
        }
        const factual = JSON.stringify(JSON.parse(readFileSync(factualCandidatePath, "utf8"))).replaceAll("<", "\\u003c");
        const structural = JSON.stringify(JSON.parse(readFileSync(phase4bCandidatePath, "utf8"))).replaceAll("<", "\\u003c");
        response.statusCode = 200;
        response.setHeader("Content-Type", "text/html; charset=utf-8");
        response.setHeader("Cache-Control", "no-store");
        response.end(`<!doctype html><meta charset="utf-8"><title>Loading local Phase-4B checkpoint</title><script>localStorage.removeItem("auxsays.localMotionQaState");localStorage.setItem("auxsays.localFactualCandidate",${JSON.stringify(factual)});localStorage.setItem("auxsays.localPhase4bState",${JSON.stringify(structural)});location.replace("/systems-monitor/?view=summary");</script>`);
      });
    }
  };
}

export default defineConfig({
  base: "/systems-monitor/",
  plugins: [localPhase4bCheckpoint()],
  build: {
    outDir: "../.build/ui",
    emptyOutDir: true,
    manifest: true,
    sourcemap: false,
    rollupOptions: {
      input: "src/main.tsx",
      output: {
        entryFileNames: "assets/[name]-[hash].js",
        chunkFileNames: "assets/[name]-[hash].js",
        assetFileNames: "assets/[name]-[hash][extname]"
      }
    }
  }
});
