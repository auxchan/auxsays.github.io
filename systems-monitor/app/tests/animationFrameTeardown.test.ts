import { describe, expect, it } from "vitest";

// Regression guard for a failed site deploy. The tests' requestAnimationFrame stand-in
// (tests/setup.ts) runs frames on timers. Frames still pending when a test file ended
// ran after vitest had torn down the jsdom environment, which deletes the global
// cancelAnimationFrame, so vitest reported "ReferenceError: cancelAnimationFrame is not
// defined" as an unhandled error and exited 1 although every test had passed.
//
// The first test ends with two kinds of work still pending:
// - a batched store notification, queued the way @reduxjs/toolkit's autoBatchEnhancer
//   (used by recharts) queues it: a frame plus a 100 ms fallback timer, both of which
//   call the bare global cancelAnimationFrame;
// - an animation loop that requests a new frame every time it runs.
// The second test then removes the frame globals, as environment teardown does, and waits
// past the fallback deadline. Anything left pending runs into the missing global. The
// shared setup must settle every pending frame after each test: dropping the frame alone
// would leave the fallback timer to fail in the same way.
// The two tests run in order and share state on purpose.

const FRAME_GLOBALS = ["requestAnimationFrame", "cancelAnimationFrame"] as const;

let notifications = 0;
let loopFrames = 0;

function queueBatchedNotification(notify: () => void) {
  let called = false;
  const callback = () => {
    if (called) return;
    called = true;
    cancelAnimationFrame(frameId);
    clearTimeout(fallbackId);
    notify();
  };
  const frameId = requestAnimationFrame(callback);
  const fallbackId = setTimeout(callback, 100);
}

function startAnimationLoop() {
  let frameId = 0;
  const step = () => {
    loopFrames += 1;
    cancelAnimationFrame(frameId);
    frameId = requestAnimationFrame(step);
  };
  frameId = requestAnimationFrame(step);
}

describe("animation frames still pending when a test ends", () => {
  it("first test: ends with a batched store notification and an animation loop pending", () => {
    startAnimationLoop();
    queueBatchedNotification(() => {
      notifications += 1;
    });
    expect(notifications).toBe(0);
  });

  it("second test: nothing pending can run once the frame globals are torn down", async () => {
    const framesBefore = loopFrames;
    const saved = FRAME_GLOBALS.map((name) => [name, Object.getOwnPropertyDescriptor(globalThis, name)] as const);
    for (const name of FRAME_GLOBALS) Reflect.deleteProperty(globalThis, name);
    try {
      await new Promise((resolve) => setTimeout(resolve, 250));
    } finally {
      for (const [name, descriptor] of saved) if (descriptor) Object.defineProperty(globalThis, name, descriptor);
    }
    expect(loopFrames).toBe(framesBefore);
    expect(notifications).toBe(1);
  });
});
