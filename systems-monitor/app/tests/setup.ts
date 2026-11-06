import { afterAll, afterEach } from "vitest";
import { cleanup } from "@testing-library/react";

// Frames requested through the requestAnimationFrame stand-in below that have not run yet.
const pendingFrames = new Map<number, FrameRequestCallback>();

// Runs every pending frame once while the test environment is still alive, then drops any
// frame those callbacks requested in turn. Vitest deletes the frame globals when it tears
// the environment down, so a frame left on its timer could run into a missing
// cancelAnimationFrame and fail the run (tests/animationFrameTeardown.test.ts). Frames are
// run rather than dropped because @reduxjs/toolkit (used by recharts) pairs each queued
// frame with a fallback timer that only the frame callback disarms.
function settlePendingFrames() {
  const due = [...pendingFrames];
  pendingFrames.clear();
  for (const [id] of due) window.clearTimeout(id);
  const failures: unknown[] = [];
  for (const [, callback] of due) {
    try {
      callback(performance.now());
    } catch (error) {
      failures.push(error);
    }
  }
  for (const id of pendingFrames.keys()) window.clearTimeout(id);
  pendingFrames.clear();
  if (failures.length > 0) throw failures[0];
}

afterEach(() => {
  cleanup();
  window.history.replaceState(null, "", "/systems-monitor/");
  settlePendingFrames();
});

afterAll(() => settlePendingFrames());

Object.defineProperty(window, "matchMedia", {
  writable: true,
  value: (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener() {},
    removeListener() {},
    addEventListener() {},
    removeEventListener() {},
    dispatchEvent: () => false
  })
});

class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
Object.defineProperty(globalThis, "ResizeObserver", { value: ResizeObserverStub });
Object.defineProperty(window, "requestAnimationFrame", {
  writable: true,
  value: (callback: FrameRequestCallback) => {
    const id = window.setTimeout(() => {
      pendingFrames.delete(id);
      callback(performance.now());
    }, 0);
    pendingFrames.set(id, callback);
    return id;
  }
});
Object.defineProperty(window, "cancelAnimationFrame", {
  writable: true,
  value: (id: number) => {
    pendingFrames.delete(id);
    window.clearTimeout(id);
  }
});
