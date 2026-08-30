import { describe, expect, it, vi } from "vitest";

vi.mock("@decky/api", () => ({ callable: () => async () => undefined }));

import {
  createDiagnosticRpc,
  decodeDiagnosticEventsResponse,
  decodeDiagnosticExportResponse,
  decodeDiagnosticSettingsResponse,
} from "../src/infra/diagnosticRpc";

const settings = {
  settings: { schemaVersion: 1, enabled: true },
  bytesUsed: 12,
  byteLimit: 52_428_800,
  eventCount: 1,
  storageDiagnostic: null,
  lastExportPath: "/home/deck/Downloads/diagnostics.txt",
};

const event = {
  sequence: 1,
  timestamp: "2026-08-30T12:00:00.000Z",
  identity: "gog:game",
  session: { pid: 321, startTime: 654 },
  category: "process",
  event: "candidate_rejected",
  outcome: "rejected",
  details: { reason: "prefix_mismatch", expected_prefix: "/a", observed_prefix: "/b" },
};

describe("diagnostic RPC boundary", () => {
  it("decodes valid settings, event, and export responses as copies", () => {
    const decodedSettings = decodeDiagnosticSettingsResponse(settings);
    const decodedEvents = decodeDiagnosticEventsResponse({
      generation: 1,
      nextCursor: "v1:1:1",
      cursorReset: false,
      events: [event],
    });
    expect(decodedSettings).toEqual(settings);
    expect(decodedSettings).not.toBe(settings);
    expect(decodedEvents.events).toEqual([event]);
    expect(decodedEvents.events[0]).not.toBe(event);
    expect(decodeDiagnosticExportResponse({ path: "/home/deck/Downloads/export.txt", bytesWritten: 42 })).toEqual({
      path: "/home/deck/Downloads/export.txt",
      bytesWritten: 42,
    });
  });

  it("decodes a privacy-bounded candidate revalidation event", () => {
    const revalidated = {
      ...event,
      event: "candidate_revalidated",
      outcome: "accepted",
      details: {
        expected_executable: "/games/game.exe",
        observed_executable: "/games/game.exe",
        expected_prefix: "/prefix",
        observed_prefix: "/prefix/pfx",
        game_id: "umu-0",
        process_name: "Main Game Threa",
        store: "gog",
        wineprefix: "/prefix/pfx",
        protonpath: "/proton",
      },
    };

    expect(
      decodeDiagnosticEventsResponse({
        generation: 1,
        nextCursor: "v1:1:1",
        cursorReset: false,
        events: [revalidated],
      }).events,
    ).toEqual([revalidated]);
  });

  it.each([
    { ...event, category: "private" },
    { ...event, outcome: "maybe" },
    { ...event, sequence: 0 },
    { ...event, session: { pid: 0, startTime: 2 } },
    { ...event, details: { token: "secret" } },
    { ...event, details: { reason: ["nested"] } },
    { ...event, details: { unexpected: "value" } },
  ])("rejects a malformed event without partially trusting it: %#", (malformed) => {
    expect(() =>
      decodeDiagnosticEventsResponse({
        generation: 1,
        nextCursor: "v1:1:1",
        cursorReset: false,
        events: [event, malformed],
      }),
    ).toThrowError("invalid_diagnostic_response");
  });

  it("clamps the request before crossing the transport and decodes all five methods", async () => {
    const getDiagnosticEvents = vi.fn().mockResolvedValue({
      generation: 1,
      nextCursor: "v1:1:1",
      cursorReset: false,
      events: [event],
    });
    const transport = {
      getDiagnosticSettings: vi.fn().mockResolvedValue(settings),
      setDiagnosticsEnabled: vi.fn().mockResolvedValue(settings),
      getDiagnosticEvents,
      exportDiagnostics: vi.fn().mockResolvedValue({ path: "/home/deck/Downloads/export.txt", bytesWritten: 42 }),
      clearDiagnostics: vi.fn().mockResolvedValue({ ...settings, generation: 2 }),
    };
    const rpc = createDiagnosticRpc(transport);

    await rpc.getDiagnosticSettings();
    await rpc.setDiagnosticsEnabled(true);
    await rpc.getDiagnosticEvents({ cursor: "v1:1:0", limit: 999 });
    await rpc.exportDiagnostics();
    await rpc.clearDiagnostics();

    expect(transport.setDiagnosticsEnabled).toHaveBeenCalledWith({ enabled: true });
    expect(getDiagnosticEvents).toHaveBeenCalledWith({ cursor: "v1:1:0", limit: 200 });
  });

  it("returns only a bounded error code for unsafe backend output", async () => {
    const rpc = createDiagnosticRpc({
      getDiagnosticSettings: vi
        .fn()
        .mockResolvedValue({ ...settings, storageDiagnostic: "private disk error /secret" }),
      setDiagnosticsEnabled: vi.fn(),
      getDiagnosticEvents: vi.fn(),
      exportDiagnostics: vi.fn(),
      clearDiagnostics: vi.fn(),
    });
    await expect(rpc.getDiagnosticSettings()).rejects.toMatchObject({ code: "invalid_diagnostic_response" });
    await expect(rpc.getDiagnosticSettings()).rejects.not.toHaveProperty("message", "private disk error /secret");
  });
});
