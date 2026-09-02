import { describe, expect, it, vi } from "vitest";

vi.mock("@decky/api", () => ({ callable: () => async () => undefined }));

import type { SymbolicHotkey } from "../src/domain/cheats/types";
import { CheatRpcError, createCheatRpc } from "../src/infra/cheatRpc";

const identity = "gog:game" as const;
const hash = "a".repeat(64);
const hotkey: SymbolicHotkey = { modifiers: ["ctrl"], key: "F1" };
const control = {
  id: "health",
  label: "Health",
  hotkey,
  state: "unknown",
};

const controlsResponse = {
  identity,
  status: "ready",
  trainerSha256: hash,
  source: "manual",
  trainerLabel: "Manual controls",
  cheats: [control],
  capabilities: { commands: true, authoritativeState: false, toggles: false },
  diagnostic: null,
};

describe("cheat RPC adapter", () => {
  it("calls the four Task 4 methods with their exact wire requests", async () => {
    const transport = {
      getCheatControls: vi.fn().mockResolvedValue(controlsResponse),
      addManualCheatControl: vi.fn().mockResolvedValue({
        identity,
        trainerSha256: hash,
        cheat: { ...control, id: "33333333-3333-4333-8333-333333333333" },
      }),
      removeManualCheatControl: vi.fn().mockResolvedValue({ identity, cheatId: control.id, removed: true }),
      sendCheatCommand: vi.fn().mockResolvedValue({
        commandId: "22222222-2222-4222-8222-222222222222",
        identity,
        cheatId: control.id,
        outcome: "requested",
        state: "unknown",
        diagnostic: null,
      }),
    };
    const rpc = createCheatRpc(transport);

    await rpc.getCheatControls(identity);
    await rpc.addManualCheatControl({ identity, trainerSha256: hash, label: " Health ", hotkey: control.hotkey });
    await rpc.removeManualCheatControl({ identity, cheatId: control.id });
    await rpc.sendCheatCommand({ identity, cheatId: control.id });

    expect(transport.getCheatControls).toHaveBeenCalledWith({ identity });
    expect(transport.addManualCheatControl).toHaveBeenCalledWith({
      identity,
      trainerSha256: hash,
      label: "Health",
      hotkey: control.hotkey,
    });
    expect(transport.removeManualCheatControl).toHaveBeenCalledWith({ identity, cheatId: control.id });
    expect(transport.sendCheatCommand).toHaveBeenCalledWith({ identity, cheatId: control.id });
  });

  it("fails closed before transport for malformed requests", async () => {
    const transport = {
      getCheatControls: vi.fn(),
      addManualCheatControl: vi.fn(),
      removeManualCheatControl: vi.fn(),
      sendCheatCommand: vi.fn(),
    };
    const rpc = createCheatRpc(transport);

    await expect(rpc.getCheatControls("steam:game" as never)).rejects.toMatchObject({ code: "invalid_identity" });
    await expect(
      rpc.addManualCheatControl({ identity, trainerSha256: "A".repeat(64), label: "Health", hotkey: control.hotkey }),
    ).rejects.toMatchObject({ code: "invalid_trainer_sha256" });
    await expect(
      rpc.addManualCheatControl({
        identity,
        trainerSha256: hash,
        label: "Health",
        hotkey: { modifiers: [], key: "VK_1" },
      }),
    ).rejects.toMatchObject({ code: "invalid_hotkey" });
    expect(transport.getCheatControls).not.toHaveBeenCalled();
    expect(transport.addManualCheatControl).not.toHaveBeenCalled();
  });

  it("maps transport failures and unsafe backend responses to bounded errors", async () => {
    const transport = {
      getCheatControls: vi.fn().mockRejectedValue(new Error("/private/trainer.exe secret-token")),
      addManualCheatControl: vi.fn(),
      removeManualCheatControl: vi.fn(),
      sendCheatCommand: vi.fn().mockResolvedValue({ ...controlsResponse, leaked: "raw" }),
    };
    const rpc = createCheatRpc(transport);

    await expect(rpc.getCheatControls(identity)).rejects.toMatchObject({ code: "cheat_rpc_failed" });
    await expect(rpc.sendCheatCommand({ identity, cheatId: "health" })).rejects.toMatchObject({
      code: "invalid_cheat_response",
    });
    await expect(rpc.getCheatControls(identity)).rejects.not.toThrow("trainer.exe");
    expect(new CheatRpcError("invalid_cheat_response")).toBeInstanceOf(Error);
  });

  it("accepts stateful results only after a decoded cooperative control snapshot", async () => {
    const cooperative = {
      ...controlsResponse,
      source: "cooperative",
      cheats: [{ id: "health", label: "Health", operations: ["toggle"], state: "unknown", authoritative: false }],
      capabilities: { commands: true, authoritativeState: false, toggles: false },
    };
    const transport = {
      getCheatControls: vi.fn().mockResolvedValue(cooperative),
      addManualCheatControl: vi.fn(),
      removeManualCheatControl: vi.fn(),
      sendCheatCommand: vi.fn().mockResolvedValue({
        commandId: "22222222-2222-4222-8222-222222222222",
        identity,
        cheatId: "health",
        outcome: "requested",
        state: "enabled",
        diagnostic: null,
      }),
    };
    const rpc = createCheatRpc(transport);

    await rpc.getCheatControls(identity);
    await expect(rpc.sendCheatCommand({ identity, cheatId: "health" })).resolves.toMatchObject({ state: "enabled" });

    transport.getCheatControls.mockResolvedValue(controlsResponse);
    await rpc.getCheatControls(identity);
    await expect(rpc.sendCheatCommand({ identity, cheatId: "health" })).rejects.toMatchObject({
      code: "cheat_state_untrusted",
    });
  });
});
