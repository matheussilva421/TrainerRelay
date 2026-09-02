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

export interface GeneratedRadialLayoutV1 {
  appId: number;
  identity: LaunchIdentity;
  trainerSha256: string;
  catalogFingerprint: string;
  steamRuntimeFingerprint: string;
  sourceLayoutId: string;
  generatedLayoutId: string;
  generatedLayoutName: string;
  revision: number;
  createdAt: string;
}

export interface RadialLayoutRegistryV1 {
  schemaVersion: 1;
  layouts: GeneratedRadialLayoutV1[];
}

export interface SteamInputMethodShape {
  getConfig: boolean;
  exportConfig: boolean;
  startEditing: boolean;
  saveEditing: boolean;
  stopEditing: boolean;
  setActionSet: boolean;
  setActivator: boolean;
  setBinding: boolean;
  setSourceMode: boolean;
  setSelected: boolean;
  showConfigurator: boolean;
  responsePrimitiveKeys: string[];
  responsePrimitiveTypes?: Record<string, string>;
  controllerClassification?: "steam_deck_builtin" | "unknown";
}

export interface SelectedLayoutSnapshot {
  appId: number;
  controllerIndex: 0;
  controller: "steam_deck_builtin";
  sourceLayoutId: string;
  sourceLayoutName: string;
  runtimeFingerprint: string;
}

export type SteamInputCapabilityResult =
  | { status: "unavailable"; diagnostic: string }
  | { status: "readonly"; snapshot: SelectedLayoutSnapshot }
  | { status: "writable"; snapshot: SelectedLayoutSnapshot };

export interface CreateRadialLayoutRequest {
  source: SelectedLayoutSnapshot;
  plan: SteamInputRadialPlanV1;
  generatedLayoutName: string;
}

export interface CreatedLayout {
  sourceLayoutId: string;
  generatedLayoutId: string;
  generatedLayoutName: string;
  selectedLayoutIdAfterSave: string;
}

export type SteamInputLayoutCreationResult =
  | { status: "unsupported_runtime"; diagnostic: string }
  | { status: "created"; layout: CreatedLayout };

export interface SteamInputLayoutAdapter {
  probe(appId: number): Promise<SteamInputCapabilityResult>;
  inspectSelectedLayout(appId: number): Promise<SelectedLayoutSnapshot>;
  createSeparateLayout(request: CreateRadialLayoutRequest): Promise<SteamInputLayoutCreationResult>;
  openConfigurator(appId: number): Promise<void>;
}

export interface SteamInputAdapterDependencies {
  input: unknown;
  app: unknown;
  digest: Sha256Digest;
}
