import { describe, expect, it, vi } from "vitest";

vi.hoisted(() => {
  vi.stubGlobal("window", {
    SP_REACT: {
      createElement: (type: unknown, props: Record<string, unknown> | null, ...children: unknown[]) => ({
        type,
        props: { ...props, children: children.length === 1 ? children[0] : children },
      }),
      Fragment: "Fragment",
    },
  });
});

vi.mock("@decky/api", () => ({ callable: () => async () => undefined }));

vi.mock("../src/infra/cheatRpc", () => ({
  CheatRpcError: class CheatRpcError extends Error {
    code: string;
    constructor(code: string) {
      super(code);
      this.code = code;
    }
  },
  cheatRpc: {},
}));

vi.mock("react", () => ({
  useEffect: vi.fn(),
  useState: <T>(initial: T) => [initial, vi.fn()],
}));

vi.mock("@decky/ui", () => {
  const component = (name: string) => name;
  return {
    ButtonItem: component("ButtonItem"),
    DialogButton: component("DialogButton"),
    DropdownItem: component("DropdownItem"),
    Field: component("Field"),
    Focusable: component("Focusable"),
    PanelSection: component("PanelSection"),
    PanelSectionRow: component("PanelSectionRow"),
    TextField: component("TextField"),
    ToggleField: component("ToggleField"),
  };
});

vi.mock("react-icons/fa", () => ({ FaGithub: "FaGithub" }));

const hookState = vi.hoisted(() => ({
  status: "unavailable" as const,
  response: undefined as unknown,
  busy: false,
  lastResults: {} as Record<string, string>,
  sendCommand: vi.fn(),
  addManualCheatControl: vi.fn(),
  removeManualCheatControl: vi.fn(),
}));

const activeIdentityState = vi.hoisted(() => ({ value: undefined as "gog:game" | undefined }));
const cheatHookCalls = vi.hoisted(() => ({ lastIdentity: undefined as string | undefined }));

vi.mock("../src/hooks/useCheatControls", async () => {
  const actual = await vi.importActual<typeof import("../src/hooks/useCheatControls")>("../src/hooks/useCheatControls");
  return {
    ...actual,
    useCheatControls: (identity: string | undefined) => {
      cheatHookCalls.lastIdentity = identity;
      return hookState;
    },
  };
});

vi.mock("../src/hooks/useActiveLaunchIdentity", () => ({
  useActiveLaunchIdentity: () => activeIdentityState.value,
}));

import { CheatControlList } from "../src/components/CheatControlList";
import { ManualCheatEditor } from "../src/components/ManualCheatEditor";
import type { ReadyCheatControls } from "../src/domain/cheats/types";
import { startCheatControlsPolling } from "../src/hooks/useCheatControls";
import Content from "../src/views/Content";

interface ElementNode {
  type?: unknown;
  props?: { children?: unknown; [key: string]: unknown };
}

const descendants = (value: unknown): ElementNode[] => {
  if (Array.isArray(value)) return value.flatMap(descendants);
  if (!value || typeof value !== "object") return [];
  const node = value as ElementNode;
  return [node, ...descendants(node.props?.children)];
};

const identity = "gog:game" as const;
const ready: ReadyCheatControls = {
  identity,
  status: "ready",
  trainerSha256: "a".repeat(64),
  source: "adapter",
  trainerLabel: "Test trainer",
  cheats: [{ id: "health", label: "Health", hotkey: { modifiers: [], key: "F1" }, state: "unknown" }],
  capabilities: { commands: true, authoritativeState: false, toggles: false },
  diagnostic: null,
};

describe("Quick Access cheat controls", () => {
  it("polls only while mounted, prevents overlapping requests, and clears its timer", async () => {
    const callbacks: Array<() => void> = [];
    const poll = vi.fn().mockResolvedValue(ready);
    const onResponse = vi.fn();
    const onError = vi.fn();
    const clearInterval = vi.fn();
    const stop = startCheatControlsPolling({
      identity,
      poll,
      onResponse,
      onError,
      setInterval: (callback) => {
        callbacks.push(callback);
        return 42;
      },
      clearInterval,
    });

    await Promise.resolve();
    expect(poll).toHaveBeenCalledOnce();
    callbacks[0]();
    callbacks[0]();
    expect(poll).toHaveBeenCalledTimes(2);
    stop();
    stop();
    callbacks[0]();
    await Promise.resolve();
    expect(clearInterval).toHaveBeenCalledWith(42);
    expect(poll).toHaveBeenCalledTimes(2);
  });

  it("reports only bounded error codes from polling", async () => {
    const onError = vi.fn();
    const stop = startCheatControlsPolling({
      identity,
      poll: vi.fn().mockRejectedValue(new Error("/private/trainer.exe secret")),
      onResponse: vi.fn(),
      onError,
      setInterval: () => 7,
      clearInterval: vi.fn(),
    });
    await Promise.resolve();
    expect(onError).toHaveBeenCalledWith("cheat_rpc_failed");
    stop();
  });

  it("refreshes controls after a command", async () => {
    const actual = await vi.importActual<typeof import("../src/hooks/useCheatControls")>(
      "../src/hooks/useCheatControls",
    );
    const rpc = {
      getCheatControls: vi.fn().mockResolvedValue(ready),
      addManualCheatControl: vi.fn(),
      removeManualCheatControl: vi.fn(),
      sendCheatCommand: vi.fn().mockResolvedValue({
        commandId: "22222222-2222-4222-8222-222222222222",
        identity,
        cheatId: "health",
        outcome: "requested",
        state: "unknown",
        diagnostic: null,
      }),
    };
    const controls = actual.useCheatControls(identity, rpc);

    await controls.sendCommand("health");
    expect(rpc.sendCheatCommand).toHaveBeenCalledWith({
      identity,
      cheatId: "health",
      allowAuthoritativeState: false,
    });
    expect(rpc.getCheatControls).toHaveBeenCalledOnce();
  });

  it("fails closed in Quick Access when no safe active identity is supplied", () => {
    activeIdentityState.value = undefined;
    const nodes = descendants(Content({}));
    expect(nodes.map((node) => node.props?.description).join(" ")).toContain("Abra a página do jogo");
    expect(nodes.some((node) => node.type === "ButtonItem")).toBe(false);
  });

  it("discovers the safe running-game identity and renders its controls", () => {
    activeIdentityState.value = identity;
    hookState.status = "ready" as never;
    hookState.response = ready;
    const nodes = descendants(Content({}));
    expect(nodes.some((node) => node.type === CheatControlList)).toBe(true);
    expect(cheatHookCalls.lastIdentity).toBe(identity);
    hookState.status = "unavailable";
    hookState.response = undefined;
    activeIdentityState.value = undefined;
  });

  it("offers the hash-bound manual editor directly in Quick Access", () => {
    activeIdentityState.value = identity;
    hookState.status = "ready" as never;
    hookState.response = {
      ...ready,
      source: "manual",
      trainerLabel: "Manual controls",
      cheats: [],
      capabilities: { commands: false, authoritativeState: false, toggles: false },
    };

    const nodes = descendants(Content({}));

    expect(nodes.some((node) => node.type === ManualCheatEditor)).toBe(true);
    hookState.status = "unavailable";
    hookState.response = undefined;
    activeIdentityState.value = undefined;
  });
});
