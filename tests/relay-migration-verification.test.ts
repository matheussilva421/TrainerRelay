import { describe, expect, it, vi } from "vitest";
import type { LaunchIdentity } from "../src/domain/relay/types";
import { verifyLegacyMigration } from "../src/hooks/migrationVerification";

const identity: LaunchIdentity = "epic:game-1";
const expectedSource = "KEEP=1 %command% epic:game-1";

interface Harness {
  emit: (snapshot: { command: string; launchOptions: string }) => void;
  fireTimeout: () => void;
  subscribe: (listener: (snapshot: { command: string; launchOptions: string }) => void) => () => void;
  setTimer: (callback: () => void, milliseconds: number) => number;
  clearTimer: ReturnType<typeof vi.fn<(handle: unknown) => void>>;
  unsubscribe: ReturnType<typeof vi.fn>;
  write: ReturnType<typeof vi.fn<(appid: number, source: string) => Promise<void>>>;
}

const harness = (): Harness => {
  let listener: ((snapshot: { command: string; launchOptions: string }) => void) | undefined;
  let timeout: (() => void) | undefined;
  const unsubscribe = vi.fn(() => {
    listener = undefined;
  });
  const subscribe = (next: (snapshot: { command: string; launchOptions: string }) => void) => {
    listener = next;
    return unsubscribe;
  };
  const setTimer = (callback: () => void) => {
    timeout = callback;
    return 1;
  };
  const write = vi.fn<(appid: number, source: string) => Promise<void>>().mockResolvedValue(undefined);
  return {
    emit: (snapshot) => listener?.(snapshot),
    fireTimeout: () => timeout?.(),
    subscribe,
    setTimer,
    clearTimer: vi.fn(),
    unsubscribe,
    write,
  };
};

const run = (testHarness: Harness, identityToUse: LaunchIdentity = identity) =>
  verifyLegacyMigration({
    appid: 42,
    identity: identityToUse,
    expectedSource,
    write: testHarness.write,
    subscribe: testHarness.subscribe,
    setTimer: testHarness.setTimer,
    clearTimer: testHarness.clearTimer,
  });

describe("legacy migration verification", () => {
  it("writes the exact proposed source and resolves only after a fresh matching snapshot", async () => {
    const testHarness = harness();
    const pending = run(testHarness);

    await Promise.resolve();
    expect(testHarness.write).toHaveBeenCalledWith(42, expectedSource);
    testHarness.emit({ command: "/usr/bin/unifideck-launcher", launchOptions: expectedSource });

    await expect(pending).resolves.toEqual({ status: "verified", identity });
    expect(testHarness.unsubscribe).toHaveBeenCalledTimes(1);
  });

  it("cancels without writing or subscribing", async () => {
    const testHarness = harness();
    await expect(
      verifyLegacyMigration({
        appid: 42,
        identity,
        expectedSource,
        cancelled: true,
        write: testHarness.write,
        subscribe: vi.fn(),
        setTimer: vi.fn(),
        clearTimer: vi.fn(),
      }),
    ).resolves.toEqual({ status: "cancelled" });
    expect(testHarness.write).not.toHaveBeenCalled();
  });

  it("rejects a fresh source mismatch and always unsubscribes", async () => {
    const testHarness = harness();
    const pending = run(testHarness);
    await Promise.resolve();
    testHarness.emit({ command: "/usr/bin/unifideck-launcher", launchOptions: "%command% epic:game-1" });

    await expect(pending).resolves.toEqual({ status: "mismatch", identity, diagnostic: "launch_options_mismatch" });
    expect(testHarness.unsubscribe).toHaveBeenCalledTimes(1);
  });

  it("rejects an identity change even when the source matches", async () => {
    const testHarness = harness();
    const pending = run(testHarness);
    await Promise.resolve();
    testHarness.emit({ command: "/usr/bin/unifideck-launcher", launchOptions: "KEEP=1 %command% gog:other" });

    await expect(pending).resolves.toEqual({ status: "identity_changed", identity });
    expect(testHarness.unsubscribe).toHaveBeenCalledTimes(1);
  });

  it("resolves timeout and writer errors as safe diagnostics with unsubscribe ownership", async () => {
    const timeoutHarness = harness();
    const timedOut = run(timeoutHarness);
    await Promise.resolve();
    timeoutHarness.fireTimeout();
    await expect(timedOut).resolves.toEqual({ status: "timeout", identity, diagnostic: "app_details_timeout" });
    expect(timeoutHarness.unsubscribe).toHaveBeenCalledTimes(1);

    const errorHarness = harness();
    errorHarness.write.mockRejectedValue(new Error("backend details"));
    await expect(run(errorHarness)).resolves.toEqual({ status: "error", identity, diagnostic: "write_failed" });
    expect(errorHarness.unsubscribe).toHaveBeenCalledTimes(1);
  });
});
