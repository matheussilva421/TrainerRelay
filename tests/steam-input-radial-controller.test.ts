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
  SteamInputCapabilityResult,
  SteamInputLayoutAdapter,
  SteamInputLayoutCreationResult,
} from "../src/domain/steamInput/types";
import {
  createSteamInputRadialMenuController,
  type SteamInputAuthority,
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

const readonlyAdapter = (
  probe: () => Promise<SteamInputCapabilityResult> = async () => ({ status: "readonly", snapshot }),
) => {
  const adapter: SteamInputLayoutAdapter = {
    probe,
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
    catalogFingerprint: "b".repeat(64),
    sourceLayoutIdHash: "d".repeat(64),
    ...overrides,
  });

describe("Steam Input radial controller", () => {
  it("moves readonly probe data to ready and keeps generation unreachable", async () => {
    const adapter = readonlyAdapter();
    const statuses: string[] = [];
    const controller = makeController(adapter, { onStateChange: (state) => statuses.push(state.status) });

    await expect(controller.prepare()).resolves.toMatchObject({ status: "ready" });
    expect(controller.getState()).toMatchObject({ status: "ready", commandCount: 1, pageCount: 1 });
    expect(controller.getState()).toMatchObject({ generationAvailable: false });

    await controller.beginConfirmation();
    expect(controller.getState().status).toBe("confirming");
    await controller.confirm();

    expect(controller.getState().status).toBe("ready");
    expect(adapter.createSeparateLayout).not.toHaveBeenCalled();
    expect(statuses).not.toContain("generating");
  });

  it.each([
    ["appId", { appId: appId + 1 }],
    ["identity", { identity: "epic:999999" }],
    ["trainer hash", { trainerSha256: "e".repeat(64) }],
    ["catalog fingerprint", { catalogFingerprint: "f".repeat(64) }],
    ["source layout", { sourceLayoutId: "autosave://changed" }],
    ["controller", { controller: "unknown" }],
    ["runtime fingerprint", { runtimeFingerprint: "e".repeat(64) }],
  ] as const)("reports authority_changed for changed %s without adapter mutation", async (_name, changed) => {
    const adapter = readonlyAdapter();
    const currentAuthority: SteamInputAuthority = {
      appId,
      identity,
      trainerSha256: controls.trainerSha256,
      catalogFingerprint: "b".repeat(64),
      sourceLayoutId: snapshot.sourceLayoutId,
      controller: snapshot.controller,
      runtimeFingerprint: snapshot.runtimeFingerprint,
    };
    const controller = makeController(adapter, {
      readAuthority: async () => ({ ...currentAuthority, ...changed }),
    });
    await controller.prepare();
    await controller.beginConfirmation();
    await expect(controller.confirm()).resolves.toMatchObject({ status: "stale" });
    expect(controller.getState()).toMatchObject({ status: "stale", reason: "authority_changed" });
    expect(adapter.createSeparateLayout).not.toHaveBeenCalled();
  });

  it("supports every state only through an injected writable fake and fails boundedly", async () => {
    let release: (() => void) | undefined;
    const writable: SteamInputLayoutAdapter = {
      probe: vi.fn(async (): Promise<SteamInputCapabilityResult> => ({ status: "writable", snapshot })),
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

    const failing = makeController({
      ...writable,
      createSeparateLayout: vi.fn(
        async (): Promise<SteamInputLayoutCreationResult> => ({
          status: "unsupported_runtime",
          diagnostic: "failed",
        }),
      ),
    });
    await failing.prepare();
    await failing.beginConfirmation();
    await expect(failing.confirm()).resolves.toMatchObject({ status: "failed", reason: "failed" });
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
