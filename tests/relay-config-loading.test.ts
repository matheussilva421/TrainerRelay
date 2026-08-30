import { afterEach, describe, expect, it, vi } from "vitest";
import { loadRelayConfigWithTimeout } from "../src/hooks/loadRelayConfig";

afterEach(() => {
  vi.useRealTimers();
});

describe("relay configuration loading", () => {
  it("fails closed when the backend never answers and ignores a late response", async () => {
    vi.useFakeTimers();
    type EmptyConfig = { schemaVersion: 1; games: Record<string, never> };
    let resolveConfig: ((value: EmptyConfig) => void) | undefined;
    const load = vi.fn(
      () =>
        new Promise<EmptyConfig>((resolve) => {
          resolveConfig = resolve;
        }),
    );
    const onReady = vi.fn();
    const onError = vi.fn();

    const cancel = loadRelayConfigWithTimeout({
      load,
      onReady,
      onError,
      setTimer: (callback, milliseconds) => setTimeout(callback, milliseconds),
      clearTimer: (handle) => clearTimeout(handle as ReturnType<typeof setTimeout>),
      timeoutMs: 5_000,
    });

    await vi.advanceTimersByTimeAsync(5_000);
    expect(onError).toHaveBeenCalledOnce();
    expect(onReady).not.toHaveBeenCalled();

    resolveConfig?.({ schemaVersion: 1, games: {} });
    await Promise.resolve();
    expect(onReady).not.toHaveBeenCalled();

    cancel();
  });
});
