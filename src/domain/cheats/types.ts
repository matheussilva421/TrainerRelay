import type { LaunchIdentity } from "../relay/types";

export type CheatSource = "adapter" | "manual" | "cooperative";
export type CheatState = "unknown" | "enabled" | "disabled";
export type CheatOperation = "enable" | "disable" | "toggle";
export type CheatControlsStatus = "unavailable" | "waiting" | "ready";
export type HotkeyModifier = "ctrl" | "alt" | "shift";

export interface SymbolicHotkey {
  modifiers: HotkeyModifier[];
  key: string;
}

export interface CheatDescriptor {
  id: string;
  label: string;
  hotkey?: SymbolicHotkey;
  hotkeys?: SymbolicHotkey[];
  operations?: CheatOperation[];
  state: CheatState;
  authoritative?: boolean;
}

export interface ReadyCheatControls {
  identity: LaunchIdentity;
  status: "ready";
  trainerSha256: string;
  source: CheatSource;
  trainerLabel: string;
  cheats: CheatDescriptor[];
  capabilities: {
    commands: boolean;
    authoritativeState: boolean;
    toggles: boolean;
  };
  diagnostic: { code: string } | null;
}

export interface InactiveCheatControls {
  identity: LaunchIdentity;
  status: "unavailable" | "waiting";
  diagnostic: { code: string } | null;
}

export type CheatControlsResponse = ReadyCheatControls | InactiveCheatControls;

export interface CheatCommandResult {
  commandId: string;
  identity: LaunchIdentity;
  cheatId: string;
  outcome: "requested" | "failed" | "rejected";
  state: CheatState;
  diagnostic: { code: string } | null;
}

export interface ManualCheatMutation {
  identity: LaunchIdentity;
  trainerSha256: string;
  cheat: CheatDescriptor;
}

export interface ManualCheatRemoval {
  identity: LaunchIdentity;
  cheatId: string;
  removed: boolean;
}
