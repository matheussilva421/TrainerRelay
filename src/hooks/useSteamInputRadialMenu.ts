import { useEffect, useRef, useState } from "react";
import type { ReadyCheatControls } from "../domain/cheats/types";
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
  SteamInputProbeEventResult,
  SteamInputProbeExportResult,
  SteamInputProbeMetadataEvent,
  SteamInputProbeObservation,
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

export interface SteamInputCurrentContext {
  appId: number;
  identity: LaunchIdentity;
  controls: ReadyCheatControls;
}

export interface SteamInputRadialMenuRpc {
  getRegistry: () => Promise<RadialLayoutRegistryV1>;
  exportProbe: (report: SteamInputProbeReport) => Promise<SteamInputProbeExportResult>;
  recordProbeEvent: (event: SteamInputProbeMetadataEvent) => Promise<SteamInputProbeEventResult>;
}

export interface SteamInputRadialMenuOptions {
  appId: number;
  identity: LaunchIdentity;
  controls: ReadyCheatControls;
  adapter: SteamInputLayoutAdapter;
  rpc: SteamInputRadialMenuRpc;
  digest?: Sha256Digest;
  getCurrentContext?: () => SteamInputCurrentContext;
  createCorrelationId?: () => string;
  onStateChange?: (state: SteamInputRadialMenuState) => void;
}

export interface SteamInputRadialMenuState {
  status: SteamInputRadialMenuStatus;
  reason: string;
  busy: boolean;
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

export interface SteamInputRadialMenuController extends SteamInputRadialMenuHookResult {
  getState: () => SteamInputRadialMenuState;
  matches: (options: SteamInputRadialMenuOptions) => boolean;
  dispose: () => void;
}

interface CurrentObservation {
  context: SteamInputCurrentContext;
  snapshot: SelectedLayoutSnapshot;
  observation: SteamInputProbeObservation;
  catalogFingerprint: string;
  sourceLayoutIdHash: string;
  authority: SteamInputAuthority;
  writable: boolean;
}

const initialState = (): SteamInputRadialMenuState => ({
  status: "ready",
  reason: "Steam Input runtime not physically validated",
  busy: false,
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

const correlationPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;

const defaultCorrelationId = (): string => {
  const cryptoApi = globalThis.crypto as Crypto & { randomUUID?: () => string };
  const value = cryptoApi?.randomUUID?.();
  if (typeof value !== "string" || !correlationPattern.test(value)) throw new Error("correlation_unavailable");
  return value;
};

const sha256Text = async (value: string, digest: Sha256Digest): Promise<string> => {
  const result = await digest(new TextEncoder().encode(value));
  if (result.length !== 32) throw new Error("invalid_sha256_digest");
  return Array.from(result, (byte) => byte.toString(16).padStart(2, "0")).join("");
};

const isRecord = (value: unknown): value is Record<string, unknown> =>
  Boolean(value) && typeof value === "object" && !Array.isArray(value);

const probeObservation = (value: unknown): SteamInputProbeObservation => {
  if (!isRecord(value) || !isRecord(value.methodShape) || !Array.isArray(value.responsePrimitiveKeys))
    throw new Error("probe_shape_unavailable");
  const methodShape = value.methodShape;
  const methodKeys = ["getConfig", "exportConfig", "startEditing", "saveEditing", "setSelected", "showConfigurator"];
  if (
    Object.keys(value).length !== 2 ||
    !Object.keys(value).every((key) => ["methodShape", "responsePrimitiveKeys"].includes(key)) ||
    Object.keys(methodShape).length !== methodKeys.length ||
    !methodKeys.every((key) => typeof methodShape[key] === "boolean") ||
    value.responsePrimitiveKeys.length > 64
  )
    throw new Error("probe_shape_unavailable");
  const keys: string[] = [];
  for (const key of value.responsePrimitiveKeys) {
    if (
      typeof key !== "string" ||
      key.length < 1 ||
      key.length > 256 ||
      !/^[A-Za-z0-9_.-]+$/.test(key) ||
      /(account|token|authorization|secret|password|cookie|credential)/i.test(key) ||
      keys.includes(key)
    )
      throw new Error("probe_shape_unavailable");
    keys.push(key);
  }
  return {
    methodShape: {
      getConfig: methodShape.getConfig as boolean,
      exportConfig: methodShape.exportConfig as boolean,
      startEditing: methodShape.startEditing as boolean,
      saveEditing: methodShape.saveEditing as boolean,
      setSelected: methodShape.setSelected as boolean,
      showConfigurator: methodShape.showConfigurator as boolean,
    },
    responsePrimitiveKeys: keys,
  };
};

const authorityFrom = (
  context: SteamInputCurrentContext,
  snapshot: SelectedLayoutSnapshot,
  catalogFingerprint: string,
): SteamInputAuthority => ({
  appId: snapshot.appId,
  identity: context.identity,
  trainerSha256: context.controls.trainerSha256,
  catalogFingerprint,
  sourceLayoutId: snapshot.sourceLayoutId,
  controller: snapshot.controller,
  runtimeFingerprint: snapshot.runtimeFingerprint,
});

const changedAuthorityFields = (
  expected: SteamInputAuthority,
  observed: SteamInputAuthority,
): (keyof SteamInputAuthority)[] => {
  const keys: (keyof SteamInputAuthority)[] = [
    "appId",
    "identity",
    "trainerSha256",
    "catalogFingerprint",
    "sourceLayoutId",
    "controller",
    "runtimeFingerprint",
  ];
  return keys.filter((key) => expected[key] !== observed[key]);
};

const skippedDetails = (controls: ReadyCheatControls): { count: number; reasons: readonly string[] } => {
  if (!controls.capabilities.commands)
    return { count: controls.cheats.length, reasons: ["Command capability disabled"] };
  const commandIds = new Set(buildSteamInputCommandItems(controls).map((item) => item.cheatId));
  const count = controls.cheats.filter((cheat) => !commandIds.has(cheat.id)).length;
  return count === 0 ? { count, reasons: [] } : { count, reasons: ["Unsupported or missing hotkey"] };
};

const stateWithPlan = (
  status: SteamInputRadialMenuStatus,
  reason: string,
  observed: CurrentObservation,
  plan: SteamInputRadialPlanV1,
): SteamInputRadialMenuState => {
  const skipped = skippedDetails(observed.context.controls);
  return {
    status,
    reason,
    busy: false,
    generationAvailable: observed.writable,
    snapshot: observed.snapshot,
    plan,
    commandCount: plan.pages.reduce((total, page) => total + page.items.length, 0),
    pageCount: plan.pages.length,
    skippedCount: skipped.count,
    skippedReasons: skipped.reasons,
  };
};

const probeReport = (observed: CurrentObservation): SteamInputProbeReport => ({
  schemaVersion: 1,
  appId: observed.snapshot.appId,
  identity: observed.context.identity,
  controller: "steam_deck_builtin",
  controllerIndex: 0,
  runtimeFingerprint: observed.snapshot.runtimeFingerprint,
  sourceLayoutIdHash: observed.sourceLayoutIdHash,
  sourceLayoutNameLength: observed.snapshot.sourceLayoutName.length,
  methodShape: observed.observation.methodShape,
  responsePrimitiveKeys: [...observed.observation.responsePrimitiveKeys],
});

export const createSteamInputRadialMenuController = (
  options: SteamInputRadialMenuOptions,
): SteamInputRadialMenuController => {
  let state = initialState();
  let disposed = false;
  let operation = 0;
  let expectedAuthority: SteamInputAuthority | undefined;
  let preparedSnapshot: SelectedLayoutSnapshot | undefined;
  let preparedPlan: SteamInputRadialPlanV1 | undefined;
  let writableRuntime = false;
  const digest = options.digest ?? defaultDigest;

  const active = (token: number): boolean => !disposed && token === operation;
  const currentContext = (): SteamInputCurrentContext =>
    options.getCurrentContext?.() ?? { appId: options.appId, identity: options.identity, controls: options.controls };

  const transition = (next: SteamInputRadialMenuState): SteamInputRadialMenuState => {
    state = next;
    options.onStateChange?.(state);
    return state;
  };

  const observeCurrent = async (token: number): Promise<CurrentObservation | undefined> => {
    if (!active(token)) return undefined;
    const context = currentContext();
    if (!active(token)) return undefined;
    const result: SteamInputCapabilityResult = await options.adapter.probe(context.appId);
    if (!active(token)) return undefined;
    if (result.status === "unavailable") throw new Error(result.diagnostic);
    const observation = probeObservation(result.observation);
    if (!active(token)) return undefined;
    const catalogFingerprint = await computeCatalogFingerprint(context.controls, digest);
    if (!active(token)) return undefined;
    const sourceLayoutIdHash = await sha256Text(result.snapshot.sourceLayoutId, digest);
    if (!active(token)) return undefined;
    return {
      context,
      snapshot: result.snapshot,
      observation,
      catalogFingerprint,
      sourceLayoutIdHash,
      authority: authorityFrom(context, result.snapshot, catalogFingerprint),
      writable: result.status === "writable",
    };
  };

  const recordMetadata = async (
    token: number,
    build: (correlationId: string) => SteamInputProbeMetadataEvent,
  ): Promise<boolean> => {
    if (!active(token)) return false;
    try {
      const correlationId = (options.createCorrelationId ?? defaultCorrelationId)();
      if (!correlationPattern.test(correlationId) || !active(token)) return active(token);
      await options.rpc.recordProbeEvent(build(correlationId));
    } catch {
      // Diagnostics are deliberately non-blocking after the exact frontend/backend boundary validates them.
    }
    return active(token);
  };

  const recordAuthorityChanged = async (
    token: number,
    observed: CurrentObservation,
    changedFieldCount: number,
  ): Promise<boolean> =>
    recordMetadata(token, (correlationId) => ({
      event: "authority_changed",
      appId: observed.context.appId,
      identity: observed.context.identity,
      changedFieldCount,
      trainerHashPrefix: observed.context.controls.trainerSha256.slice(0, 12),
      catalogFingerprintPrefix: observed.catalogFingerprint.slice(0, 12),
      runtimeFingerprintPrefix: observed.snapshot.runtimeFingerprint.slice(0, 12),
      sourceLayoutIdHashPrefix: observed.sourceLayoutIdHash.slice(0, 12),
      resultCode: "authority_changed",
      correlationId,
    }));

  const prepare = async (): Promise<SteamInputRadialMenuState> => {
    const token = ++operation;
    transition({ ...state, busy: true });
    try {
      const observed = await observeCurrent(token);
      if (!observed || !active(token)) return state;
      if (observed.snapshot.appId !== observed.context.appId || observed.snapshot.controller !== "steam_deck_builtin")
        throw new Error("authority_unavailable");
      const nextPlan = buildSteamInputRadialPlan({
        appId: observed.context.appId,
        identity: observed.context.identity,
        trainerSha256: observed.context.controls.trainerSha256,
        catalogFingerprint: observed.catalogFingerprint,
        controls: observed.context.controls,
      });
      if (!active(token)) return state;

      let stale = false;
      try {
        if (!active(token)) return state;
        const registry = await options.rpc.getRegistry();
        if (!active(token)) return state;
        stale = registry.layouts.some(
          (layout) =>
            layout.appId === observed.context.appId &&
            layout.identity === observed.context.identity &&
            layout.trainerSha256 === observed.context.controls.trainerSha256 &&
            layout.catalogFingerprint === observed.catalogFingerprint &&
            (layout.sourceLayoutId !== observed.snapshot.sourceLayoutId ||
              layout.steamRuntimeFingerprint !== observed.snapshot.runtimeFingerprint),
        );
      } catch {
        if (!active(token)) return state;
      }

      const nextState = stateWithPlan(
        stale ? "stale" : "ready",
        stale ? "authority_changed" : "Steam Input runtime not physically validated",
        observed,
        nextPlan,
      );
      const recorded = await recordMetadata(token, (correlationId) => ({
        event: "preview_created",
        appId: observed.context.appId,
        identity: observed.context.identity,
        commandCount: nextState.commandCount,
        pageCount: nextState.pageCount,
        skippedCount: nextState.skippedCount,
        trainerHashPrefix: observed.context.controls.trainerSha256.slice(0, 12),
        catalogFingerprintPrefix: observed.catalogFingerprint.slice(0, 12),
        runtimeFingerprintPrefix: observed.snapshot.runtimeFingerprint.slice(0, 12),
        sourceLayoutIdHashPrefix: observed.sourceLayoutIdHash.slice(0, 12),
        resultCode: "readonly",
        correlationId,
      }));
      if (!recorded || !active(token)) return state;

      expectedAuthority = observed.authority;
      preparedSnapshot = observed.snapshot;
      preparedPlan = nextPlan;
      writableRuntime = observed.writable;
      return transition(nextState);
    } catch (reason) {
      if (!active(token)) return state;
      const code = reason instanceof Error ? reason.message : reason;
      return transition({ ...initialState(), status: "unavailable", reason: safeReason(code) });
    }
  };

  const beginConfirmation = async (): Promise<SteamInputRadialMenuState> => {
    if (state.busy || state.status !== "ready" || !preparedSnapshot || !preparedPlan) return state;
    return transition({ ...state, status: "confirming", reason: "Review the read-only radial menu preview" });
  };

  const confirm = async (): Promise<SteamInputRadialMenuState> => {
    if (state.status !== "confirming" || !expectedAuthority || !preparedSnapshot || !preparedPlan) return state;
    const token = ++operation;
    transition({
      ...state,
      status: writableRuntime ? "generating" : "confirming",
      reason: "Revalidating Steam Input authority",
      busy: true,
    });
    try {
      const observed = await observeCurrent(token);
      if (!observed || !active(token)) return state;
      const changed = changedAuthorityFields(expectedAuthority, observed.authority);
      if (changed.length > 0) {
        if (!(await recordAuthorityChanged(token, observed, changed.length)) || !active(token)) return state;
        return transition({ ...state, status: "stale", reason: "authority_changed", busy: false });
      }
      if (!observed.writable)
        return transition({
          ...state,
          status: "ready",
          reason: "Steam Input runtime not physically validated",
          busy: false,
        });

      if (!active(token)) return state;
      const result = await options.adapter.createSeparateLayout({
        source: preparedSnapshot,
        plan: preparedPlan,
        generatedLayoutName: `Trainer Relay — ${observed.context.identity} — ${observed.context.controls.trainerSha256.slice(0, 8)} — r1`,
      });
      if (!active(token)) return state;
      if (result.status !== "created")
        return transition({ ...state, status: "failed", reason: safeReason(result.diagnostic), busy: false });
      if (
        result.layout.generatedLayoutId === result.layout.sourceLayoutId ||
        result.layout.selectedLayoutIdAfterSave !== result.layout.sourceLayoutId
      )
        return transition({ ...state, status: "failed", reason: "layout_invariant_failed", busy: false });
      return transition({
        ...state,
        status: "created",
        reason: "separate_layout_created",
        layout: result.layout,
        busy: false,
      });
    } catch (reason) {
      if (!active(token)) return state;
      return transition({
        ...state,
        status: "failed",
        reason: safeReason(reason instanceof Error ? reason.message : reason),
        busy: false,
      });
    }
  };

  const exportSafeProbe = async (): Promise<SteamInputProbeExportResult | undefined> => {
    if (!expectedAuthority) await prepare();
    if (state.status !== "ready" || !expectedAuthority) return undefined;
    const token = ++operation;
    transition({ ...state, busy: true });
    try {
      const observed = await observeCurrent(token);
      if (!observed || !active(token)) return undefined;
      const changed = changedAuthorityFields(expectedAuthority, observed.authority);
      if (changed.length > 0) {
        if (!(await recordAuthorityChanged(token, observed, changed.length)) || !active(token)) return undefined;
        transition({ ...state, status: "stale", reason: "authority_changed", busy: false });
        return undefined;
      }
      const report = probeReport(observed);
      if (!active(token)) return undefined;
      const result = await options.rpc.exportProbe(report);
      if (!active(token)) return undefined;
      transition({ ...state, busy: false, exportResult: result });
      return result;
    } catch (reason) {
      if (!active(token)) return undefined;
      transition({
        ...state,
        status: "failed",
        reason: safeReason(reason instanceof Error ? reason.message : reason),
        busy: false,
      });
      return undefined;
    }
  };

  const openConfigurator = async (): Promise<void> => {
    const token = ++operation;
    const context = currentContext();
    transition({ ...state, busy: true });
    try {
      if (!active(token)) return;
      await options.adapter.openConfigurator(context.appId);
      if (!active(token)) return;
      const recorded = await recordMetadata(token, (correlationId) => ({
        event: "configurator_opened",
        appId: context.appId,
        identity: context.identity,
        resultCode: "opened",
        correlationId,
      }));
      if (recorded && active(token)) transition({ ...state, busy: false });
    } catch (reason) {
      if (!active(token)) return;
      const code = safeReason(reason instanceof Error ? reason.message : reason);
      transition({ ...state, status: "failed", reason: code, busy: false });
      throw new Error(code);
    }
  };

  return {
    get state() {
      return state;
    },
    getState: () => state,
    matches: (next) =>
      next.appId === options.appId && next.identity === options.identity && next.controls === options.controls,
    prepare,
    beginConfirmation,
    confirm,
    exportSafeProbe,
    openConfigurator,
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
