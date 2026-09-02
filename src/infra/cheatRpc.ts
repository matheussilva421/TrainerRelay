import { callable } from "@decky/api";
import {
  CheatDecodeError,
  decodeCheatCommandResult,
  decodeCheatControlsResponse,
  decodeCheatId,
  decodeHotkey,
  decodeLabel,
  decodeLaunchIdentity,
  decodeManualMutation,
  decodeManualRemoval,
  decodeTrainerSha256,
} from "../domain/cheats/decoder";
import type {
  CheatCommandResult,
  CheatControlsResponse,
  ManualCheatMutation,
  ManualCheatRemoval,
  SymbolicHotkey,
} from "../domain/cheats/types";
import type { LaunchIdentity } from "../domain/relay/types";

export interface CheatRpcTransport {
  getCheatControls: (request: { identity: LaunchIdentity }) => Promise<unknown>;
  addManualCheatControl: (request: {
    identity: LaunchIdentity;
    trainerSha256: string;
    label: string;
    hotkey: SymbolicHotkey;
  }) => Promise<unknown>;
  removeManualCheatControl: (request: { identity: LaunchIdentity; cheatId: string }) => Promise<unknown>;
  sendCheatCommand: (request: { identity: LaunchIdentity; cheatId: string }) => Promise<unknown>;
}

export interface CheatRpcClient {
  getCheatControls: (identity: LaunchIdentity) => Promise<CheatControlsResponse>;
  addManualCheatControl: (request: {
    identity: LaunchIdentity;
    trainerSha256: string;
    label: string;
    hotkey: SymbolicHotkey;
  }) => Promise<ManualCheatMutation>;
  removeManualCheatControl: (request: { identity: LaunchIdentity; cheatId: string }) => Promise<ManualCheatRemoval>;
  sendCheatCommand: (request: {
    identity: LaunchIdentity;
    cheatId: string;
    allowAuthoritativeState?: boolean;
  }) => Promise<CheatCommandResult>;
}

export class CheatRpcError extends Error {
  constructor(readonly code: string) {
    super(code);
    this.name = "CheatRpcError";
  }
}

const guarded = async <T>(operation: () => Promise<T>): Promise<T> => {
  try {
    return await operation();
  } catch (error) {
    if (error instanceof CheatRpcError) throw error;
    if (error instanceof CheatDecodeError) throw new CheatRpcError(error.code);
    throw new CheatRpcError("cheat_rpc_failed");
  }
};

export const createCheatRpc = (transport: CheatRpcTransport): CheatRpcClient => ({
  getCheatControls(identity) {
    return guarded(async () => {
      const normalized = decodeLaunchIdentity(identity);
      return decodeCheatControlsResponse(normalized, await transport.getCheatControls({ identity: normalized }));
    });
  },
  addManualCheatControl(request) {
    return guarded(async () => {
      const normalized = {
        identity: decodeLaunchIdentity(request.identity),
        trainerSha256: decodeTrainerSha256(request.trainerSha256),
        label: decodeLabel(request.label.trim()),
        hotkey: decodeHotkey(request.hotkey),
      };
      return decodeManualMutation(normalized.identity, await transport.addManualCheatControl(normalized));
    });
  },
  removeManualCheatControl(request) {
    return guarded(async () => {
      const identity = decodeLaunchIdentity(request.identity);
      const cheatId = decodeCheatId(request.cheatId);
      return decodeManualRemoval(identity, cheatId, await transport.removeManualCheatControl({ identity, cheatId }));
    });
  },
  sendCheatCommand(request) {
    return guarded(async () => {
      const identity = decodeLaunchIdentity(request.identity);
      const cheatId = decodeCheatId(request.cheatId);
      return decodeCheatCommandResult(identity, cheatId, await transport.sendCheatCommand({ identity, cheatId }), {
        allowAuthoritativeState: request.allowAuthoritativeState === true,
      });
    });
  },
});

const getCheatControlsCall = callable<[{ identity: LaunchIdentity }], unknown>("get_cheat_controls");
const addManualCheatControlCall = callable<
  [{ identity: LaunchIdentity; trainerSha256: string; label: string; hotkey: SymbolicHotkey }],
  unknown
>("add_manual_cheat_control");
const removeManualCheatControlCall = callable<[{ identity: LaunchIdentity; cheatId: string }], unknown>(
  "remove_manual_cheat_control",
);
const sendCheatCommandCall = callable<[{ identity: LaunchIdentity; cheatId: string }], unknown>("send_cheat_command");

export const cheatRpc = createCheatRpc({
  getCheatControls: (request) => getCheatControlsCall(request),
  addManualCheatControl: (request) => addManualCheatControlCall(request),
  removeManualCheatControl: (request) => removeManualCheatControlCall(request),
  sendCheatCommand: (request) => sendCheatCommandCall(request),
});
