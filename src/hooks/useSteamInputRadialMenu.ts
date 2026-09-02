import { useEffect, useRef, useState } from "react";
import type { LaunchIdentity } from "../domain/relay/types";
import {
  buildSteamInputCommandItems,
  buildSteamInputRadialPlan,
  computeCatalogFingerprint,
} from "../domain/steamInput/planner";
import type {
  CreatedLayout,
  RadialLayoutRegistryV1,
  SelectedLayoutSnapshot,
  Sha256Digest,
  SteamInputCapabilityResult,
  SteamInputLayoutAdapter,
  SteamInputProbeExportResult,
  SteamInputProbeReport,
  SteamInputRadialPlanV1,
} from "../domain/steamInput/types";

export type SteamInputRadialMenuStatus =
  | "unavailable"
  | "ready"
  | "confirming"
  | "generating"
  | "created"
  | "stale"
  | "failed";

export interface SteamInputAuthority {
  appId: number;
  identity: LaunchIdentity;
  trainerSha256: string;
  catalogFingerprint: string;
  sourceLayoutId: string;
  controller: string;
  runtimeFingerprint: string;
}

export interface SteamInputRadialMenuRpc {
  getRegistry: () => Promise<RadialLayoutRegistryV1>;
  exportProbe: (report: SteamInputProbeReport) => Promise<SteamInputProbeExportResult>;
}

export interface SteamInputRadialMenuOptions {
  appId: number;
  identity: SteamInputAuthority["identity"];
  controls: Parameters<typeof buildSteamInputRadialPlan>[0]["controls"];
  adapter: SteamInputLayoutAdapter;
  rpc: SteamInputRadialMenuRpc;
  catalogFingerprint?: string;
  sourceLayoutIdHash?: string;
  digest?: Sha256Digest;
  readAuthority?: () => Promise<SteamInputAuthority>;
  onStateChange?: (state: SteamInputRadialMenuState) => void;
}

export interface SteamInputRadialMenuState {
  status: SteamInputRadialMenuStatus;
  reason: string;
  generationAvailable: boolean;
  snapshot?: SelectedLayoutSnapshot;
  plan?: SteamInputRadialPlanV1;
  commandCount: number;
  pageCount: number;
  skippedCount: number;
  skippedReasons: readonly string[];
  layout?: CreatedLayout;
  exportResult?: SteamInputProbeExportResult;
}

export interface SteamInputRadialMenuHookResult {
  state: SteamInputRadialMenuState;
  prepare: () => Promise<SteamInputRadialMenuState>;
  beginConfirmation: () => Promise<SteamInputRadialMenuState>;
  confirm: () => Promise<SteamInputRadialMenuState>;
  exportSafeProbe: () => Promise<SteamInputProbeExportResult | undefined>;
  openConfigurator: () => Promise<void>;
}

export interface SteamInputRadialMenuController {
  getState: () => SteamInputRadialMenuState;
  matches: (options: SteamInputRadialMenuOptions) => boolean;
  prepare: () => Promise<SteamInputRadialMenuState>;
  beginConfirmation: () => Promise<SteamInputRadialMenuState>;
  confirm: () => Promise<SteamInputRadialMenuState>;
  exportSafeProbe: () => Promise<SteamInputProbeExportResult | undefined>;
  openConfigurator: () => Promise<void>;
  dispose: () => void;
}

const initialState = (): SteamInputRadialMenuState => ({
  status: "ready",
  reason: "Steam Input runtime not physically validated",
  generationAvailable: false,
  commandCount: 0,
  pageCount: 0,
  skippedCount: 0,
  skippedReasons: [],
});

const safeReason = (reason: unknown): string =>
  typeof reason === "string" && /^[a-z0-9_ -]{1,128}$/i.test(reason) ? reason : "steam_input_unavailable";

const defaultDigest: Sha256Digest = async (value) => {
  if (!globalThis.crypto?.subtle) throw new Error("digest_unavailable");
  return new Uint8Array(await globalThis.crypto.subtle.digest("SHA-256", value as unknown as BufferSource));
};

const sha256Text = async (value: string, digest: Sha256Digest): Promise<string> => {
  const result = await digest(new TextEncoder().encode(value));
  if (result.length !== 32) throw new Error("invalid_sha256_digest");
  return Array.from(result, (byte) => byte.toString(16).padStart(2, "0")).join("");
};

const authorityFromSnapshot = (
  options: SteamInputRadialMenuOptions,
  snapshot: SelectedLayoutSnapshot,
  catalogFingerprint: string,
): SteamInputAuthority => ({
  appId: snapshot.appId,
  identity: options.identity,
  trainerSha256: options.controls.trainerSha256,
  catalogFingerprint,
  sourceLayoutId: snapshot.sourceLayoutId,
  controller: snapshot.controller,
  runtimeFingerprint: snapshot.runtimeFingerprint,
});

const changedAuthorityField = (
  expected: SteamInputAuthority,
  observed: SteamInputAuthority,
): keyof SteamInputAuthority | undefined => {
  const keys: (keyof SteamInputAuthority)[] = [
    "appId",
    "identity",
    "trainerSha256",
    "catalogFingerprint",
    "sourceLayoutId",
    "controller",
    "runtimeFingerprint",
  ];
  return keys.find((key) => expected[key] !== observed[key]);
};

const skippedDetails = (
  controls: SteamInputRadialMenuOptions["controls"],
): {
  count: number;
  reasons: readonly string[];
} => {
  if (!controls.capabilities.commands)
    return { count: controls.cheats.length, reasons: ["Command capability disabled"] };
  const commandIds = new Set(buildSteamInputCommandItems(controls).map((item) => item.cheatId));
  const count = controls.cheats.filter((cheat) => !commandIds.has(cheat.id)).length;
  return count === 0 ? { count, reasons: [] } : { count, reasons: ["Unsupported or missing hotkey"] };
};

const stateWithPlan = (
  status: SteamInputRadialMenuStatus,
  reason: string,
  snapshot: SelectedLayoutSnapshot,
  plan: SteamInputRadialPlanV1,
  controls: SteamInputRadialMenuOptions["controls"],
  generationAvailable: boolean,
): SteamInputRadialMenuState => {
  const skipped = skippedDetails(controls);
  return {
    status,
    reason,
    generationAvailable,
    snapshot,
    plan,
    commandCount: plan.pages.reduce((total, page) => total + page.items.length, 0),
    pageCount: plan.pages.length,
    skippedCount: skipped.count,
    skippedReasons: skipped.reasons,
  };
};

const probeReport = (
  identity: LaunchIdentity,
  snapshot: SelectedLayoutSnapshot,
  sourceLayoutIdHash: string,
  runtimeFingerprint: string,
): SteamInputProbeReport => ({
  schemaVersion: 1,
  appId: snapshot.appId,
  identity,
  controller: "steam_deck_builtin",
  controllerIndex: 0,
  runtimeFingerprint,
  sourceLayoutIdHash,
  sourceLayoutNameLength: snapshot.sourceLayoutName.length,
  methodShape: {
    getConfig: true,
    exportConfig: false,
    startEditing: false,
    saveEditing: false,
    setSelected: false,
    showConfigurator: true,
  },
  responsePrimitiveKeys: ["controller_type", "url"],
});

export const createSteamInputRadialMenuController = (
  options: SteamInputRadialMenuOptions,
): SteamInputRadialMenuController => {
  let state = initialState();
  let disposed = false;
  let operation = 0;
  let snapshot: SelectedLayoutSnapshot | undefined;
  let plan: SteamInputRadialPlanV1 | undefined;
  let catalogFingerprint = options.catalogFingerprint;
  let sourceLayoutIdHash = options.sourceLayoutIdHash;
  let writableRuntime = false;

  const transition = (next: SteamInputRadialMenuState): SteamInputRadialMenuState => {
    state = next;
    options.onStateChange?.(state);
    return state;
  };

  const readAuthority = async (): Promise<{ authority: SteamInputAuthority; writable: boolean }> => {
    if (options.readAuthority) return { authority: await options.readAuthority(), writable: writableRuntime };
    const result = await options.adapter.probe(options.appId);
    if (result.status === "unavailable") throw new Error(result.diagnostic);
    const currentCatalog =
      catalogFingerprint ?? (await computeCatalogFingerprint(options.controls, options.digest ?? defaultDigest));
    return {
      authority: authorityFromSnapshot(options, result.snapshot, currentCatalog),
      writable: result.status === "writable",
    };
  };

  const prepare = async (): Promise<SteamInputRadialMenuState> => {
    const token = ++operation;
    try {
      const result: SteamInputCapabilityResult = await options.adapter.probe(options.appId);
      if (disposed || token !== operation) return state;
      if (result.status === "unavailable")
        return transition({ ...initialState(), status: "unavailable", reason: safeReason(result.diagnostic) });
      if (result.snapshot.appId !== options.appId || result.snapshot.controller !== "steam_deck_builtin")
        return transition({ ...initialState(), status: "unavailable", reason: "authority_unavailable" });

      catalogFingerprint ??= await computeCatalogFingerprint(options.controls, options.digest ?? defaultDigest);
      sourceLayoutIdHash ??= await sha256Text(result.snapshot.sourceLayoutId, options.digest ?? defaultDigest);
      const nextPlan = buildSteamInputRadialPlan({
        appId: options.appId,
        identity: options.identity,
        trainerSha256: options.controls.trainerSha256,
        catalogFingerprint,
        controls: options.controls,
      });
      snapshot = result.snapshot;
      plan = nextPlan;
      writableRuntime = result.status === "writable";

      let stale = false;
      try {
        const registry = await options.rpc.getRegistry();
        stale = registry.layouts.some(
          (layout) =>
            layout.appId === options.appId &&
            layout.identity === options.identity &&
            layout.trainerSha256 === options.controls.trainerSha256 &&
            layout.catalogFingerprint === catalogFingerprint &&
            (layout.sourceLayoutId !== result.snapshot.sourceLayoutId ||
              layout.steamRuntimeFingerprint !== result.snapshot.runtimeFingerprint),
        );
      } catch {
        stale = false;
      }
      return transition(
        stateWithPlan(
          stale ? "stale" : "ready",
          stale ? "authority_changed" : "Steam Input runtime not physically validated",
          result.snapshot,
          nextPlan,
          options.controls,
          writableRuntime,
        ),
      );
    } catch (reason) {
      if (disposed || token !== operation) return state;
      const code = reason instanceof Error ? reason.message : reason;
      return transition({ ...initialState(), status: "unavailable", reason: safeReason(code) });
    }
  };

  const beginConfirmation = async (): Promise<SteamInputRadialMenuState> => {
    if (state.status !== "ready" || !snapshot || !plan) return state;
    return transition({ ...state, status: "confirming", reason: "Review the read-only radial menu preview" });
  };

  const confirm = async (): Promise<SteamInputRadialMenuState> => {
    if (state.status !== "confirming" || !snapshot || !plan) return state;
    const token = ++operation;
    try {
      if (writableRuntime) transition({ ...state, status: "generating", reason: "Revalidating Steam Input authority" });
      const current = await readAuthority();
      if (disposed || token !== operation) return state;
      const expected = authorityFromSnapshot(options, snapshot, catalogFingerprint ?? plan.catalogFingerprint);
      const changed = changedAuthorityField(expected, current.authority);
      if (changed) return transition({ ...state, status: "stale", reason: "authority_changed" });
      if (!current.writable)
        return transition({ ...state, status: "ready", reason: "Steam Input runtime not physically validated" });

      const result = await options.adapter.createSeparateLayout({
        source: snapshot,
        plan,
        generatedLayoutName: `Trainer Relay — ${options.identity} — ${options.controls.trainerSha256.slice(0, 8)} — r1`,
      });
      if (result.status !== "created")
        return transition({ ...state, status: "failed", reason: safeReason(result.diagnostic) });
      if (
        result.layout.generatedLayoutId === result.layout.sourceLayoutId ||
        result.layout.selectedLayoutIdAfterSave !== result.layout.sourceLayoutId
      )
        return transition({ ...state, status: "failed", reason: "layout_invariant_failed" });
      return transition({ ...state, status: "created", reason: "separate_layout_created", layout: result.layout });
    } catch (reason) {
      if (disposed || token !== operation) return state;
      return transition({
        ...state,
        status: "failed",
        reason: safeReason(reason instanceof Error ? reason.message : reason),
      });
    }
  };

  const exportSafeProbe = async (): Promise<SteamInputProbeExportResult | undefined> => {
    if (!snapshot) await prepare();
    if (!snapshot || !sourceLayoutIdHash) return undefined;
    const report = probeReport(options.identity, snapshot, sourceLayoutIdHash, snapshot.runtimeFingerprint);
    const result = await options.rpc.exportProbe(report);
    transition({ ...state, exportResult: result });
    return result;
  };

  return {
    getState: () => state,
    matches: (next) =>
      next.appId === options.appId && next.identity === options.identity && next.controls === options.controls,
    prepare,
    beginConfirmation,
    confirm,
    exportSafeProbe,
    openConfigurator: () => options.adapter.openConfigurator(options.appId),
    dispose: () => {
      disposed = true;
      operation += 1;
    },
  };
};

export const useSteamInputRadialMenu = (options: SteamInputRadialMenuOptions): SteamInputRadialMenuHookResult => {
  const [state, setState] = useState<SteamInputRadialMenuState>(initialState());
  const controllerRef = useRef<SteamInputRadialMenuController>();
  if (!controllerRef.current?.matches(options))
    controllerRef.current = createSteamInputRadialMenuController({ ...options, onStateChange: setState });
  const controller = controllerRef.current;

  useEffect(() => {
    void controller.prepare();
    return controller.dispose;
  }, [controller]);

  return {
    state,
    prepare: controller.prepare,
    beginConfirmation: controller.beginConfirmation,
    confirm: controller.confirm,
    exportSafeProbe: controller.exportSafeProbe,
    openConfigurator: controller.openConfigurator,
  };
};
