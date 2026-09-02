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

  it("decodes all bounded Steam Input probe events", () => {
    const steamEvents = [
      {
        ...event,
        category: "steam_input",
        event: "probe_completed",
        outcome: "accepted",
        details: {
          app_id: 123456789,
          primitive_key_count: 2,
          runtime_fingerprint_prefix: "c".repeat(12),
          trainer_hash_prefix: "a".repeat(12),
          catalog_fingerprint_prefix: "b".repeat(12),
          source_layout_id_hash_prefix: "d".repeat(12),
          result_code: "readonly",
          correlation_id: "11111111-1111-4111-8111-111111111111",
        },
      },
      {
        ...event,
        category: "steam_input",
        event: "preview_created",
        outcome: "accepted",
        details: {
          app_id: 123456789,
          command_count: 2,
          page_count: 1,
          skipped_count: 0,
          trainer_hash_prefix: "a".repeat(12),
          catalog_fingerprint_prefix: "b".repeat(12),
          runtime_fingerprint_prefix: "c".repeat(12),
          source_layout_id_hash_prefix: "d".repeat(12),
          correlation_id: "22222222-2222-4222-8222-222222222222",
        },
      },
      {
        ...event,
        category: "steam_input",
        event: "authority_changed",
        outcome: "rejected",
        details: {
          app_id: 123456789,
          changed_field_count: 1,
          trainer_hash_prefix: "a".repeat(12),
          catalog_fingerprint_prefix: "b".repeat(12),
          runtime_fingerprint_prefix: "c".repeat(12),
          source_layout_id_hash_prefix: "d".repeat(12),
          result_code: "authority_changed",
          correlation_id: "33333333-3333-4333-8333-333333333333",
        },
      },
      {
        ...event,
        category: "steam_input",
        event: "configurator_opened",
        outcome: "accepted",
        details: {
          app_id: 123456789,
          result_code: "opened",
          correlation_id: "44444444-4444-4444-8444-444444444444",
        },
      },
    ];

    expect(
      decodeDiagnosticEventsResponse({
        generation: 1,
        nextCursor: "v1:1:4",
        cursorReset: false,
        events: steamEvents,
      }).events,
    ).toEqual(steamEvents);
  });

  it("decodes every backend-allowlisted UMU and command diagnostic shape", () => {
    const commandId = "11111111-1111-4111-8111-111111111111";
    const allowlisted = [
      {
        category: "umu",
        event: "container_reentry_verified",
        details: {
          bus_name: "com.example.Runtime",
          runtime_variant: "umu",
          attempt_count: 1,
          bus_source: "host",
          app_id_source: "gameid",
          service_marker_present: true,
        },
      },
      {
        category: "umu",
        event: "container_reentry_rejected",
        details: {
          reason: "bus_missing",
          failure_class: "unavailable",
          probe_exit_code: 1,
          bus_source: "host",
          attempt_count: 2,
          service_marker_present: false,
        },
      },
      { category: "umu", event: "container_reentry_confirmed", details: { bus_name: "runtime", elapsed_ms: 12 } },
      {
        category: "umu",
        event: "container_reentry_confirmation_failed",
        details: { bus_name: "runtime", elapsed_ms: 12, failure_observed: true, service_marker_present: false },
      },
      {
        category: "umu",
        event: "umu_exit_diagnostics",
        details: {
          stdout_bytes: 2,
          stderr_bytes: 0,
          stdout_truncated: false,
          stderr_truncated: false,
          stdout_tail: "ok",
          stderr_tail: "",
          failure_class: "none",
          group_member_count: 1,
          group_member_names: "trainer",
          observed_descendant_count: 1,
          observed_descendant_names: "trainer",
        },
      },
      {
        category: "trainer",
        event: "trainer_spawned",
        details: {
          trainer_path: "/trainer.exe",
          process_group_id: 12,
          wineprefix: "/prefix",
          steam_compat_data_path: "/compat",
          proton_verb: "runinprefix",
          container_reentry: true,
          environment_key_count: 8,
          runtime_flags: "verified",
        },
      },
      { category: "command", event: "catalog_loaded", details: { adapter_count: 1 } },
      { category: "command", event: "catalog_rejected", details: { reason: "hash_mismatch" } },
      { category: "command", event: "manual_control_added", details: { cheat_id: "health", control_count: 1 } },
      { category: "command", event: "manual_control_removed", details: { cheat_id: "health", control_count: 0 } },
      {
        category: "command",
        event: "command_rejected",
        details: { command_id: commandId, cheat_id: "health", reason: "stale" },
      },
      {
        category: "command",
        event: "helper_spawned",
        details: { command_id: commandId, cheat_id: "health", source: "manual" },
      },
      {
        category: "command",
        event: "helper_completed",
        details: { command_id: commandId, cheat_id: "health", source: "manual", outcome: "requested", duration_ms: 12 },
      },
      { category: "command", event: "helper_timeout", details: { command_id: commandId, cheat_id: "health" } },
      {
        category: "command",
        event: "cooperative_acknowledged",
        details: { command_id: commandId, cheat_id: "health", revision: 2 },
      },
      {
        category: "command",
        event: "cooperative_stale",
        details: { command_id: commandId, cheat_id: "health", revision: 2, reason: "stale" },
      },
      { category: "command", event: "cooperative_descriptor_rejected", details: { reason: "invalid_descriptor" } },
    ].map((candidate, index) => ({ ...event, ...candidate, sequence: index + 1 }));

    expect(
      decodeDiagnosticEventsResponse({
        generation: 1,
        nextCursor: `v1:1:${allowlisted.length}`,
        cursorReset: false,
        events: allowlisted,
      }).events,
    ).toEqual(allowlisted);
  });

  it.each([
    {
      ...event,
      category: "command",
      event: "helper_spawned",
      details: { command_id: "11111111-1111-4111-8111-111111111111", cheat_id: "health", source: "private" },
    },
    { ...event, category: "umu", event: "umu_exit_diagnostics", details: { stdout_tail: "x".repeat(1025) } },
  ])("rejects diagnostic metadata that the backend allowlist rejects", (candidate) => {
    expect(() =>
      decodeDiagnosticEventsResponse({ generation: 1, nextCursor: "v1:1:1", cursorReset: false, events: [candidate] }),
    ).toThrowError("invalid_diagnostic_response");
  });

  it("decodes the effective UMU shape of a trainer spawn", () => {
    const spawned = {
      ...event,
      category: "trainer",
      event: "trainer_spawned",
      outcome: "accepted",
      details: {
        trainer_path: "/games/trainer.exe",
        process_group_id: 789,
        wineprefix: "/prefix",
        steam_compat_data_path: "/prefix",
        proton_verb: "runinprefix",
      },
    };

    expect(
      decodeDiagnosticEventsResponse({
        generation: 1,
        nextCursor: "v1:1:1",
        cursorReset: false,
        events: [spawned],
      }).events,
    ).toEqual([spawned]);
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
