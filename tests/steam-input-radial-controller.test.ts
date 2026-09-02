import { describe, expect, it, vi } from "vitest";

vi.mock("react", () => ({
  useEffect: vi.fn(),
  useRef: <T>() => ({ current: null as T | null }),
  useState: <T>(initial: T) => [initial, vi.fn()],
}));

import type { ReadyCheatControls } from "../src/domain/cheats/types";
import type {
  RadialLayoutRegistryV1,
  SelectedLayoutSnapshot,
  Sha256Digest,
  SteamInputCapabilityResult,
  SteamInputLayoutAdapter,
  SteamInputLayoutCreationResult,
  SteamInputProbeObservation,
} from "../src/domain/steamInput/types";
import {
  createSteamInputRadialMenuController,
  type SteamInputRadialMenuController,
} from "../src/hooks/useSteamInputRadialMenu";

const appId = 123456789;
const identity = "gog:1482265668" as const;
const snapshot: SelectedLayoutSnapshot = {
  appId,
  controllerIndex: 0,
  controller: "steam_deck_builtin",
  sourceLayoutId: "autosave://source",
  sourceLayoutName: "Source Layout",
  runtimeFingerprint: "c".repeat(64),
};
const observation: SteamInputProbeObservation = {
  methodShape: {
    getConfig: true,
    exportConfig: true,
    startEditing: false,
    saveEditing: false,
    setSelected: false,
    showConfigurator: true,
  },
  responsePrimitiveKeys: ["controller_type", "url", "name"],
};
const controls: ReadyCheatControls = {
  identity,
  status: "ready",
  trainerSha256: "a".repeat(64),
  source: "manual",
  trainerLabel: "Manual trainer",
  cheats: [{ id: "health", label: "Health", hotkey: { modifiers: [], key: "F1" }, state: "unknown" }],
  capabilities: { commands: true, authoritativeState: false, toggles: false },
  diagnostic: null,
};

const deterministicDigest: Sha256Digest = async (value) => {
  const text = new TextDecoder().decode(value);
  if (text.startsWith("autosave://changed")) return new Uint8Array(32).fill(0xee);
  if (text.startsWith("autosave://")) return new Uint8Array(32).fill(0xdd);
  if (text.includes("Changed catalog")) return new Uint8Array(32).fill(0xff);
  return new Uint8Array(32).fill(0xbb);
};

const readonlyAdapter = (
  probe: (probeAppId: number) => Promise<SteamInputCapabilityResult> = async (probeAppId) => ({
    status: "readonly",
    snapshot: { ...snapshot, appId: probeAppId },
    observation,
  }),
) => {
  const adapter: SteamInputLayoutAdapter = {
    probe: vi.fn(probe),
    inspectSelectedLayout: async () => snapshot,
    createSeparateLayout: vi.fn(
      async (): Promise<SteamInputLayoutCreationResult> => ({
        status: "unsupported_runtime",
        diagnostic: "not allowed",
      }),
    ),
    openConfigurator: vi.fn(async () => undefined),
  };
  return adapter;
};

const rpc = () => ({
  getRegistry: vi.fn(async (): Promise<RadialLayoutRegistryV1> => ({ schemaVersion: 1, layouts: [] })),
  exportProbe: vi.fn(async () => ({ path: "/home/deck/Downloads/probe.json", bytesWritten: 10 })),
  recordProbeEvent: vi.fn(async () => ({ accepted: true as const })),
});

const makeController = (
  adapter: SteamInputLayoutAdapter = readonlyAdapter(),
  overrides: Partial<Parameters<typeof createSteamInputRadialMenuController>[0]> = {},
): SteamInputRadialMenuController =>
  createSteamInputRadialMenuController({
    appId,
    identity,
    controls,
    adapter,
    rpc: rpc(),
    digest: deterministicDigest,
    createCorrelationId: () => "11111111-1111-4111-8111-111111111111",
    ...overrides,
  });

describe("Steam Input radial controller", () => {
  it("emits preview and configurator metadata while keeping readonly generation unreachable", async () => {
    const adapter = readonlyAdapter();
    const client = rpc();
    const statuses: string[] = [];
    const controller = makeController(adapter, { rpc: client, onStateChange: (state) => statuses.push(state.status) });

    await expect(controller.prepare()).resolves.toMatchObject({ status: "ready" });
    expect(controller.getState()).toMatchObject({ status: "ready", commandCount: 1, pageCount: 1 });
    expect(controller.getState()).toMatchObject({ generationAvailable: false });
    expect(client.recordProbeEvent).toHaveBeenCalledWith({
      event: "preview_created",
      appId,
      identity,
      commandCount: 1,
      pageCount: 1,
      skippedCount: 0,
      trainerHashPrefix: "a".repeat(12),
      catalogFingerprintPrefix: "b".repeat(12),
      runtimeFingerprintPrefix: "c".repeat(12),
      sourceLayoutIdHashPrefix: "d".repeat(12),
      resultCode: "readonly",
      correlationId: "11111111-1111-4111-8111-111111111111",
    });

    await controller.beginConfirmation();
    expect(controller.getState().status).toBe("confirming");
    await controller.confirm();
    await controller.openConfigurator();

    expect(controller.getState().status).toBe("ready");
    expect(adapter.createSeparateLayout).not.toHaveBeenCalled();
    expect(statuses).not.toContain("generating");
    expect(client.recordProbeEvent).toHaveBeenCalledWith({
      event: "configurator_opened",
      appId,
      identity,
      resultCode: "opened",
      correlationId: "11111111-1111-4111-8111-111111111111",
    });
  });

  const authorityMutations = [
    "appId",
    "identity",
    "trainer hash",
    "catalog fingerprint",
    "source layout",
    "controller",
    "runtime fingerprint",
  ] as const;

  it.each([
    "confirm",
    "export",
  ] as const)("recomputes every authority field before %s and blocks stale work", async (action) => {
    for (const mutation of authorityMutations) {
      let currentAppId = appId;
      let currentIdentity: ReadyCheatControls["identity"] = identity;
      let currentControls = controls;
      let currentSnapshot = snapshot;
      const adapter = readonlyAdapter(async (probeAppId) => ({
        status: "readonly",
        snapshot: { ...currentSnapshot, appId: probeAppId } as SelectedLayoutSnapshot,
        observation,
      }));
      const client = rpc();
      const controller = makeController(adapter, {
        rpc: client,
        getCurrentContext: () => ({ appId: currentAppId, identity: currentIdentity, controls: currentControls }),
      });
      await controller.prepare();

      if (mutation === "appId") currentAppId += 1;
      if (mutation === "identity") currentIdentity = "epic:changed";
      if (mutation === "trainer hash") currentControls = { ...controls, trainerSha256: "e".repeat(64) };
      if (mutation === "catalog fingerprint") {
        currentControls = { ...controls, cheats: [{ ...controls.cheats[0], label: "Changed catalog" }] };
      }
      if (mutation === "source layout") currentSnapshot = { ...snapshot, sourceLayoutId: "autosave://changed" };
      if (mutation === "controller") currentSnapshot = { ...snapshot, controller: "unknown" as never };
      if (mutation === "runtime fingerprint") currentSnapshot = { ...snapshot, runtimeFingerprint: "e".repeat(64) };

      if (action === "confirm") {
        await controller.beginConfirmation();
        await controller.confirm();
      } else {
        await expect(controller.exportSafeProbe()).resolves.toBeUndefined();
      }

      expect(controller.getState(), `${action}: ${mutation}`).toMatchObject({
        status: "stale",
        reason: "authority_changed",
      });
      expect(adapter.createSeparateLayout).not.toHaveBeenCalled();
      expect(client.exportProbe).not.toHaveBeenCalled();
      expect(client.recordProbeEvent).toHaveBeenCalledWith(
        expect.objectContaining({
          event: "authority_changed",
          changedFieldCount: expect.any(Number),
          resultCode: "authority_changed",
        }),
      );
    }
  });

  it("exports the exact current adapter observation instead of hardcoded method metadata", async () => {
    const actualObservation: SteamInputProbeObservation = {
      methodShape: {
        getConfig: true,
        exportConfig: true,
        startEditing: true,
        saveEditing: true,
        setSelected: true,
        showConfigurator: false,
      },
      responsePrimitiveKeys: ["controller_type", "url", "name", "revision"],
    };
    const adapter = readonlyAdapter(async (probeAppId) => ({
      status: "readonly",
      snapshot: { ...snapshot, appId: probeAppId },
      observation: actualObservation,
    }));
    const client = rpc();
    const controller = makeController(adapter, { rpc: client });

    await controller.prepare();
    await controller.exportSafeProbe();

    expect(client.exportProbe).toHaveBeenCalledWith(
      expect.objectContaining({
        methodShape: actualObservation.methodShape,
        responsePrimitiveKeys: actualObservation.responsePrimitiveKeys,
      }),
    );
    expect(adapter.probe).toHaveBeenCalledTimes(2);
  });

  it("fails closed when the adapter cannot provide observed probe shape", async () => {
    const adapter = readonlyAdapter(async () => ({ status: "readonly", snapshot }) as SteamInputCapabilityResult);
    const client = rpc();
    const controller = makeController(adapter, { rpc: client });

    await expect(controller.prepare()).resolves.toMatchObject({
      status: "unavailable",
      reason: "probe_shape_unavailable",
    });
    await expect(controller.exportSafeProbe()).resolves.toBeUndefined();
    expect(client.exportProbe).not.toHaveBeenCalled();
  });

  it("guards asynchronous revalidation results with the operation token before export", async () => {
    let digestCalls = 0;
    let releaseDigest: ((value: Uint8Array) => void) | undefined;
    let markDigestStarted: (() => void) | undefined;
    const digestStarted = new Promise<void>((resolve) => {
      markDigestStarted = resolve;
    });
    const digest: Sha256Digest = async (value) => {
      digestCalls += 1;
      if (digestCalls === 3) {
        markDigestStarted?.();
        return new Promise<Uint8Array>((resolve) => {
          releaseDigest = resolve;
        });
      }
      return deterministicDigest(value);
    };
    const client = rpc();
    const controller = makeController(readonlyAdapter(), { rpc: client, digest });
    await controller.prepare();

    const pending = controller.exportSafeProbe();
    await digestStarted;
    const stateWhilePending = controller.getState();
    expect(stateWhilePending.busy).toBe(true);
    controller.dispose();
    releaseDigest?.(new Uint8Array(32).fill(0xbb));

    await expect(pending).resolves.toBeUndefined();
    expect(controller.getState()).toBe(stateWhilePending);
    expect(client.exportProbe).not.toHaveBeenCalled();
  });

  it("supports generating only through an injected writable fake", async () => {
    let release: (() => void) | undefined;
    const writable: SteamInputLayoutAdapter = {
      probe: vi.fn(async (): Promise<SteamInputCapabilityResult> => ({ status: "writable", snapshot, observation })),
      inspectSelectedLayout: vi.fn(async () => snapshot),
      createSeparateLayout: vi.fn(
        () =>
          new Promise<SteamInputLayoutCreationResult>((resolve) => {
            release = () =>
              resolve({
                status: "created",
                layout: {
                  sourceLayoutId: snapshot.sourceLayoutId,
                  generatedLayoutId: "personal://generated",
                  generatedLayoutName: "Trainer Relay - test",
                  selectedLayoutIdAfterSave: snapshot.sourceLayoutId,
                },
              });
          }),
      ),
      openConfigurator: vi.fn(async () => undefined),
    };
    const controller = makeController(writable);
    await controller.prepare();
    await controller.beginConfirmation();
    const pending = controller.confirm();
    expect(controller.getState().status).toBe("generating");
    await vi.waitFor(() => expect(release).toBeTypeOf("function"));
    release?.();
    await expect(pending).resolves.toMatchObject({ status: "created" });
  });

  it("reports unavailable probe and stale registry without attempting generation", async () => {
    const unavailable = makeController(
      readonlyAdapter(async () => ({ status: "unavailable", diagnostic: "read_failed" })),
    );
    await expect(unavailable.prepare()).resolves.toMatchObject({ status: "unavailable", reason: "read_failed" });

    const staleRpc = rpc();
    staleRpc.getRegistry.mockResolvedValue({
      schemaVersion: 1,
      layouts: [
        {
          appId,
          identity,
          trainerSha256: controls.trainerSha256,
          catalogFingerprint: "b".repeat(64),
          steamRuntimeFingerprint: "z".repeat(64),
          sourceLayoutId: snapshot.sourceLayoutId,
          generatedLayoutId: "personal://old",
          generatedLayoutName: "Old",
          revision: 1,
          createdAt: "2026-09-02T12:00:00Z",
        },
      ],
    });
    const stale = makeController(readonlyAdapter(), { rpc: staleRpc });
    await expect(stale.prepare()).resolves.toMatchObject({ status: "stale" });
  });
});
