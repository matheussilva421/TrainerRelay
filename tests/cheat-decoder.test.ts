import { describe, expect, it } from "vitest";

import {
  CheatDecodeError,
  decodeCheatCommandResult,
  decodeCheatControlsResponse,
  formatHotkey,
} from "../src/domain/cheats/decoder";

const identity = "gog:game" as const;
const hash = "a".repeat(64);
const health = {
  id: "health",
  label: "Health",
  hotkey: { modifiers: ["shift", "ctrl"], key: "F1" },
  state: "unknown",
};

const ready = (overrides: Record<string, unknown> = {}) => ({
  identity,
  status: "ready",
  trainerSha256: hash,
  source: "adapter",
  trainerLabel: "Test trainer",
  cheats: [health],
  capabilities: { commands: true, authoritativeState: false, toggles: false },
  diagnostic: null,
  ...overrides,
});

const command = (overrides: Record<string, unknown> = {}) => ({
  commandId: "22222222-2222-4222-8222-222222222222",
  identity,
  cheatId: "health",
  outcome: "requested",
  state: "unknown",
  diagnostic: null,
  ...overrides,
});

describe("cheat wire decoder", () => {
  it("normalizes finite symbolic hotkeys and preserves command-only adapter semantics", () => {
    const response = decodeCheatControlsResponse(identity, ready());

    expect(response.status).toBe("ready");
    if (response.status !== "ready") throw new Error("expected ready response");
    expect(response.source).toBe("adapter");
    expect(response.cheats[0].hotkey).toEqual({ modifiers: ["ctrl", "shift"], key: "F1" });
    expect(response.cheats[0].state).toBe("unknown");
    const hotkey = response.cheats[0].hotkey;
    expect(hotkey).toBeDefined();
    if (!hotkey) throw new Error("expected hotkey");
    expect(formatHotkey(hotkey)).toBe("Ctrl + Shift + F1");
  });

  it("rejects malformed identities, hashes, hotkeys, extra fields, and unsafe diagnostics", () => {
    const cases: Array<Record<string, unknown>> = [
      { identity: "steam:game" },
      { trainerSha256: "A".repeat(64) },
      { cheats: [{ ...health, hotkey: { modifiers: ["ctrl", "ctrl"], key: "F1" } }] },
      { cheats: [{ ...health, hotkey: { modifiers: [], key: "VK_1" } }] },
      { extra: "rejected" },
      { diagnostic: { code: "trainer.exe secret-token" }, status: "waiting" },
    ];

    for (const override of cases) {
      expect(() => decodeCheatControlsResponse(identity, ready(override))).toThrow(CheatDecodeError);
    }
  });

  it("rejects enabled or disabled state without cooperative authority", () => {
    expect(() =>
      decodeCheatControlsResponse(
        identity,
        ready({
          source: "manual",
          cheats: [{ ...health, state: "enabled" }],
        }),
      ),
    ).toThrow("cheat_state_untrusted");

    expect(() =>
      decodeCheatControlsResponse(
        identity,
        ready({
          source: "cooperative",
          cheats: [{ id: "health", label: "Health", state: "enabled", operations: ["toggle"] }],
          capabilities: { commands: true, authoritativeState: false, toggles: false },
        }),
      ),
    ).toThrow("cheat_state_untrusted");
  });

  it("accepts a cooperative state only when the response is explicitly authoritative", () => {
    const response = decodeCheatControlsResponse(
      identity,
      ready({
        source: "cooperative",
        cheats: [
          {
            id: "health",
            label: "Health",
            operations: ["toggle"],
            state: "disabled",
            authoritative: true,
          },
        ],
        capabilities: { commands: true, authoritativeState: true, toggles: true },
      }),
    );

    expect(response.status).toBe("ready");
    if (response.status !== "ready") throw new Error("expected ready response");
    expect(response.cheats[0].authoritative).toBe(true);
    expect(response.capabilities.toggles).toBe(true);
  });

  it("accepts an empty manual response only as a hash-bound editor without commands", () => {
    const response = decodeCheatControlsResponse(
      identity,
      ready({
        source: "manual",
        trainerLabel: "Manual controls",
        cheats: [],
        capabilities: { commands: false, authoritativeState: false, toggles: false },
      }),
    );

    expect(response.status).toBe("ready");
    if (response.status !== "ready") throw new Error("expected ready response");
    expect(response.cheats).toEqual([]);
    expect(response.capabilities.commands).toBe(false);

    expect(() =>
      decodeCheatControlsResponse(
        identity,
        ready({
          source: "manual",
          cheats: [],
          capabilities: { commands: true, authoritativeState: false, toggles: false },
        }),
      ),
    ).toThrow("invalid_cheat_response");
  });

  it("keeps adapter/manual command results unknown and requires authority for a stateful result", () => {
    expect(decodeCheatCommandResult(identity, "health", command()).state).toBe("unknown");
    expect(() => decodeCheatCommandResult(identity, "health", command({ state: "enabled" }))).toThrow(
      "cheat_state_untrusted",
    );

    expect(
      decodeCheatCommandResult(identity, "health", command({ state: "enabled" }), {
        allowAuthoritativeState: true,
      }).state,
    ).toBe("enabled");
  });
});
