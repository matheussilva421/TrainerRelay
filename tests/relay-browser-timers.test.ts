import { describe, expect, it } from "vitest";

describe("browser timer bindings", () => {
  it("preserves the browser receiver for interval and timeout methods", async () => {
    const events: string[] = [];
    const timerScope = {
      setInterval(this: unknown, _callback: () => void, milliseconds: number) {
        if (this !== timerScope) throw new TypeError("Illegal invocation");
        events.push(`setInterval:${milliseconds}`);
        return 11;
      },
      clearInterval(this: unknown, handle: number) {
        if (this !== timerScope) throw new TypeError("Illegal invocation");
        events.push(`clearInterval:${handle}`);
      },
      setTimeout(this: unknown, _callback: () => void, milliseconds: number) {
        if (this !== timerScope) throw new TypeError("Illegal invocation");
        events.push(`setTimeout:${milliseconds}`);
        return 22;
      },
      clearTimeout(this: unknown, handle: number) {
        if (this !== timerScope) throw new TypeError("Illegal invocation");
        events.push(`clearTimeout:${handle}`);
      },
    };

    const { bindBrowserTimers } = await import("../src/hooks/browserTimers");
    const timers = bindBrowserTimers(timerScope);
    const interval = timers.setInterval(() => undefined, 1_000);
    timers.clearInterval(interval);
    const timeout = timers.setTimeout(() => undefined, 2_000);
    timers.clearTimeout(timeout);

    expect(events).toEqual(["setInterval:1000", "clearInterval:11", "setTimeout:2000", "clearTimeout:22"]);
  });
});
