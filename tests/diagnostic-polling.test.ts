import { describe, expect, it, vi } from "vitest";

import { startDiagnosticPolling } from "../src/hooks/diagnosticPolling";

const settings = (enabled: boolean) => ({
  settings: { schemaVersion: 1 as const, enabled },
  bytesUsed: 0,
  byteLimit: 52_428_800 as const,
  eventCount: 0,
  storageDiagnostic: null,
  lastExportPath: null,
});

class ManualTimers {
  callbacks: Array<() => void> = [];
  delays: number[] = [];
  cleared: unknown[] = [];
  nextHandle = 0;

  setTimeout = (callback: () => void, delay: number): unknown => {
    this.callbacks.push(callback);
    this.delays.push(delay);
    this.nextHandle += 1;
    return this.nextHandle;
  };

  clearTimeout = (handle: unknown): void => {
    this.cleared.push(handle);
  };

  fire(): void {
    const callback = this.callbacks.shift();
    if (!callback) throw new Error("no timer");
    callback();
  }
}

const settle = async () => {
  await Promise.resolve();
  await Promise.resolve();
  await Promise.resolve();
};

describe("diagnostic polling", () => {
  it("checks immediately, advances cursors, handles reset, pauses while disabled, and cleans up", async () => {
    const timers = new ManualTimers();
    const loadSettings = vi
      .fn()
      .mockResolvedValueOnce(settings(true))
      .mockResolvedValueOnce(settings(true))
      .mockResolvedValue(settings(false));
    const loadEvents = vi
      .fn()
      .mockResolvedValueOnce({ generation: 1, nextCursor: "v1:1:1", cursorReset: false, events: [{ sequence: 1 }] })
      .mockResolvedValueOnce({ generation: 2, nextCursor: "v1:2:1", cursorReset: true, events: [{ sequence: 1 }] });
    const onEvents = vi.fn();
    const stop = startDiagnosticPolling({
      loadSettings,
      loadEvents,
      onEvents,
      onSettings: vi.fn(),
      onError: vi.fn(),
      timers,
    });

    await settle();
    expect(loadEvents).toHaveBeenNthCalledWith(1, { cursor: undefined, limit: 200 });
    expect(onEvents).toHaveBeenNthCalledWith(1, [{ sequence: 1 }]);
    expect(timers.delays).toEqual([1_000]);

    timers.fire();
    await settle();
    expect(loadEvents).toHaveBeenNthCalledWith(2, { cursor: "v1:1:1", limit: 200 });
    expect(onEvents).toHaveBeenNthCalledWith(2, [{ sequence: 1 }]);

    timers.fire();
    await settle();
    expect(loadEvents).toHaveBeenCalledTimes(2);
    stop();
    expect(timers.cleared).toEqual([3]);
  });

  it("backs off 2s, 4s, 8s, then 10s and resets after recovery with one error per episode", async () => {
    const timers = new ManualTimers();
    const loadSettings = vi
      .fn()
      .mockRejectedValueOnce(new Error("private one"))
      .mockRejectedValueOnce(new Error("private two"))
      .mockRejectedValueOnce(new Error("private three"))
      .mockRejectedValueOnce(new Error("private four"))
      .mockResolvedValue(settings(false));
    const onError = vi.fn();
    startDiagnosticPolling({
      loadSettings,
      loadEvents: vi.fn(),
      onEvents: vi.fn(),
      onSettings: vi.fn(),
      onError,
      timers,
    });

    await settle();
    for (let index = 0; index < 4; index += 1) {
      timers.fire();
      await settle();
    }
    expect(timers.delays).toEqual([2_000, 4_000, 8_000, 10_000, 1_000]);
    expect(onError).toHaveBeenCalledTimes(1);
  });

  it("ignores a late promise and schedules nothing after cleanup", async () => {
    const timers = new ManualTimers();
    let resolveSettings: ((value: ReturnType<typeof settings>) => void) | undefined;
    const loadSettings = vi.fn(
      () => new Promise<ReturnType<typeof settings>>((resolve) => (resolveSettings = resolve)),
    );
    const onSettings = vi.fn();
    const stop = startDiagnosticPolling({
      loadSettings,
      loadEvents: vi.fn(),
      onEvents: vi.fn(),
      onSettings,
      onError: vi.fn(),
      timers,
    });
    stop();
    resolveSettings?.(settings(false));
    await settle();
    expect(onSettings).not.toHaveBeenCalled();
    expect(timers.delays).toEqual([]);
  });
});
