import { beforeEach, describe, expect, it, vi } from "vitest";

vi.hoisted(() => {
  vi.stubGlobal("window", {
    SP_REACT: {
      createElement: (type: unknown, props: unknown, ...children: unknown[]) => ({ type, props, children }),
      Fragment: "Fragment",
    },
    setInterval: vi.fn(),
    clearInterval: vi.fn(),
    setTimeout: vi.fn(() => 1),
    clearTimeout: vi.fn(),
  });
});

vi.mock("@decky/api", () => ({
  callable: () => async () => undefined,
  routerHook: { addRoute: vi.fn(), removeRoute: vi.fn() },
}));
vi.mock("@decky/ui", () => ({
  definePlugin: (factory: () => unknown) => factory(),
  staticClasses: { Title: "Title" },
}));
vi.mock("react-icons/fa", () => ({ FaWrench: "FaWrench" }));
vi.mock("../src/patch", () => ({ default: () => ({ unpatch: vi.fn() }), LibraryContextMenu: {} }));
vi.mock("../src/views/Content", () => ({ default: "Content" }));
vi.mock("../src/views/PageRouter", () => ({ default: "PageRouter" }));
vi.mock("../src/utils/logger", () => ({ logger: { info: vi.fn() } }));

import * as bridgeModule from "../src/diagnostics/consoleBridge";

const response = {
  settings: { schemaVersion: 1 as const, enabled: true },
  bytesUsed: 0,
  byteLimit: 52_428_800 as const,
  eventCount: 1,
  storageDiagnostic: null,
  lastExportPath: "/home/deck/Downloads/private-export-path.txt",
};

const event = {
  sequence: 1,
  timestamp: "2026-08-30T12:00:00.000Z",
  category: "process" as const,
  event: "candidate_rejected",
  outcome: "rejected" as const,
  details: { reason: "prefix_mismatch" },
};

const settle = async () => {
  await Promise.resolve();
  await Promise.resolve();
  await Promise.resolve();
};

describe("diagnostic DevTools bridge", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("logs only sanitized events with the exact prefix and one bounded warning per failure episode", async () => {
    let timer: (() => void) | undefined;
    const timers = {
      setTimeout: (callback: () => void) => {
        timer = callback;
        return 1;
      },
      clearTimeout: vi.fn(),
    };
    const info = vi.spyOn(console, "info").mockImplementation(() => undefined);
    const warn = vi.spyOn(console, "warn").mockImplementation(() => undefined);
    const rpc = {
      getDiagnosticSettings: vi.fn().mockResolvedValueOnce(response).mockRejectedValue(new Error("private RPC text")),
      getDiagnosticEvents: vi
        .fn()
        .mockResolvedValue({ generation: 1, nextCursor: "v1:1:1", cursorReset: false, events: [event] }),
    };

    const stop = bridgeModule.startDiagnosticConsoleBridge(rpc, timers);
    await settle();
    expect(info).toHaveBeenCalledWith("[TrainerRelay:diagnostic]", event);
    expect(JSON.stringify(info.mock.calls)).not.toContain("private-export-path");

    timer?.();
    await settle();
    timer?.();
    await settle();
    expect(warn).toHaveBeenCalledTimes(1);
    expect(warn).toHaveBeenCalledWith("[TrainerRelay:diagnostic] polling_unavailable");
    expect(JSON.stringify(warn.mock.calls)).not.toContain("private RPC text");
    stop();
    expect(timers.clearTimeout).toHaveBeenCalled();
  });

  it("starts once during plugin registration and stops on dismount", async () => {
    const stop = vi.fn();
    const start = vi.spyOn(bridgeModule, "startDiagnosticConsoleBridge").mockReturnValue(stop);
    const plugin = (await import("../src/index")).default as { onDismount: () => void };
    expect(start).toHaveBeenCalledTimes(1);
    plugin.onDismount();
    expect(stop).toHaveBeenCalledTimes(1);
  });
});
