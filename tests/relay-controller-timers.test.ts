import type {} from "@decky/ui";
import { afterEach, describe, expect, it, vi } from "vitest";

const reactHarness = vi.hoisted(() => ({ cleanups: [] as Array<() => void> }));

vi.mock("react", () => ({
  useEffect: (effect: () => undefined | (() => void)) => {
    const cleanup = effect();
    if (cleanup) reactHarness.cleanups.push(cleanup);
  },
  useMemo: <T>(factory: () => T) => factory(),
  useState: <T>(initial: T | (() => T)) => [typeof initial === "function" ? (initial as () => T)() : initial, vi.fn()],
}));

vi.mock("../src/hooks/useRelayAppDetails", () => ({
  useRelayAppDetails: () => ({
    details: {
      status: "ready",
      snapshot: {
        command: "/home/deck/homebrew/plugins/Unifideck/bin/unifideck-launcher",
        launchOptions: "gog:482265568",
      },
    },
    subscribe: vi.fn(),
    writeLaunchOptions: vi.fn(),
  }),
}));

vi.mock("../src/infra/decky", () => ({ browseFiles: vi.fn(), getHomePath: vi.fn(), sendNotice: vi.fn() }));

vi.mock("../src/infra/relayRpc", () => {
  const config = { schemaVersion: 1 as const, games: {} };
  return {
    emptyRelayConfig: () => config,
    persistRelayGameConfig: vi.fn(),
    relayRpc: {
      getRelayConfig: vi.fn().mockResolvedValue(config),
      setRelayGameConfig: vi.fn(),
      getRelayStatus: vi.fn().mockResolvedValue({
        identity: "gog:482265568",
        state: "waiting_for_game",
        diagnostic: null,
      }),
      retryRelay: vi.fn(),
    },
  };
});

import { useRelayPageController } from "../src/hooks/useRelayPageController";

afterEach(() => {
  reactHarness.cleanups.splice(0).forEach((cleanup) => {
    cleanup();
  });
  vi.unstubAllGlobals();
});

describe("Relay page browser timers", () => {
  it("mounts supported shortcut polling without an illegal timer invocation", () => {
    const events: string[] = [];
    const timerScope = {
      setInterval(this: unknown, _callback: () => void, milliseconds: number) {
        if (this !== timerScope) throw new TypeError("Illegal invocation");
        events.push(`set:${milliseconds}`);
        return 17;
      },
      clearInterval(this: unknown, handle: number) {
        if (this !== timerScope) throw new TypeError("Illegal invocation");
        events.push(`clear:${handle}`);
      },
      setTimeout: vi.fn(),
      clearTimeout: vi.fn(),
    };
    vi.stubGlobal("window", timerScope);

    expect(() => useRelayPageController(48_226_5568)).not.toThrow();
    reactHarness.cleanups.splice(0).forEach((cleanup) => {
      cleanup();
    });
    expect(events).toEqual(["set:1000", "clear:17"]);
  });
});
