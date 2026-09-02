import type { ReadyCheatControls, SymbolicHotkey } from "../cheats/types";
import type { LaunchIdentity } from "../relay/types";

export interface SteamInputCommandItem {
  itemId: string;
  cheatId: string;
  label: string;
  hotkey: SymbolicHotkey;
}

export interface SteamInputRadialPage {
  page: number;
  items: SteamInputCommandItem[];
  previousPage?: number;
  nextPage?: number;
}

export interface SteamInputRadialPlanV1 {
  schemaVersion: 1;
  appId: number;
  identity: LaunchIdentity;
  trainerSha256: string;
  catalogFingerprint: string;
  controller: "steam_deck_builtin";
  input: "left_trackpad";
  activation: "physical_click";
  pages: SteamInputRadialPage[];
}

export interface BuildRadialPlanInput {
  appId: number;
  identity: LaunchIdentity;
  trainerSha256: string;
  catalogFingerprint: string;
  controls: ReadyCheatControls;
}

export type Sha256Digest = (value: Uint8Array) => Promise<Uint8Array>;
