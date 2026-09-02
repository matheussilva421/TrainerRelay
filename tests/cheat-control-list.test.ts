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

vi.mock("@decky/ui", () => {
  const component = (name: string) => name;
  return {
    ButtonItem: component("ButtonItem"),
    Field: component("Field"),
    Focusable: component("Focusable"),
    ToggleField: component("ToggleField"),
  };
});

import { CheatControlList } from "../src/components/CheatControlList";
import type { ReadyCheatControls } from "../src/domain/cheats/types";

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
const hash = "a".repeat(64);

const controls = (overrides: Partial<ReadyCheatControls> = {}): ReadyCheatControls => ({
  identity,
  status: "ready",
  trainerSha256: hash,
  source: "adapter",
  trainerLabel: "Test trainer",
  cheats: [{ id: "health", label: "Infinite health", hotkey: { modifiers: ["ctrl"], key: "F1" }, state: "unknown" }],
  capabilities: { commands: true, authoritativeState: false, toggles: false },
  diagnostic: null,
  ...overrides,
});

describe("CheatControlList", () => {
  it("renders adapter controls as focused command-only rows with the exact unknown result", async () => {
    const onCommand = vi.fn().mockResolvedValue({
      commandId: "22222222-2222-4222-8222-222222222222",
      identity,
      cheatId: "health",
      outcome: "requested",
      state: "unknown",
      diagnostic: null,
    });
    const nodes = descendants(CheatControlList({ controls: controls(), busy: false, onCommand, lastResults: {} }));
    const button = nodes.find((node) => node.type === "ButtonItem");

    expect(nodes.filter((node) => node.type === "ButtonItem")).toHaveLength(1);
    expect(nodes.some((node) => node.type === "ToggleField")).toBe(false);
    expect(button?.props?.label).toBe("Infinite health");
    expect(button?.props?.description).toContain("Ctrl + F1");
    expect(button?.props?.onClick).toBe(button?.props?.onActivate);

    expect(button).toBeDefined();
    const onClick = button?.props?.onClick as () => Promise<void>;
    await onClick();
    expect(onCommand).toHaveBeenCalledWith("health");

    const resultNodes = descendants(
      CheatControlList({
        controls: controls(),
        busy: false,
        onCommand,
        lastResults: { health: "Comando enviado; estado desconhecido" },
      }),
    );
    expect(resultNodes.map((node) => node.props?.description).join(" ")).toContain(
      "Comando enviado; estado desconhecido",
    );
  });

  it("disables every command while busy", () => {
    const nodes = descendants(CheatControlList({ controls: controls(), busy: true, onCommand: vi.fn() }));
    expect(nodes.filter((node) => node.type === "ButtonItem").every((node) => node.props?.disabled === true)).toBe(
      true,
    );
  });

  it("uses a toggle only for fresh cooperative authoritative state and applicable operations", () => {
    const cooperative = controls({
      source: "cooperative",
      capabilities: { commands: true, authoritativeState: true, toggles: true },
      cheats: [
        {
          id: "god-mode",
          label: "God mode",
          state: "disabled",
          authoritative: true,
          operations: ["toggle"],
        },
      ],
    });
    const onCommand = vi.fn().mockResolvedValue(undefined);
    const nodes = descendants(CheatControlList({ controls: cooperative, busy: false, onCommand }));
    const toggle = nodes.find((node) => node.type === "ToggleField");

    expect(toggle?.props?.checked).toBe(false);
    expect(toggle?.props?.disabled).toBe(false);
    expect(nodes.some((node) => node.type === "ButtonItem")).toBe(false);
    expect(toggle).toBeDefined();
    const onChange = toggle?.props?.onChange as (checked: boolean) => void;
    onChange(true);
    expect(onCommand).toHaveBeenCalledWith("god-mode");
  });

  it("falls back to a command-only row when cooperative authority or operation applicability is missing", () => {
    const cases: ReadyCheatControls[] = [
      controls({
        source: "cooperative",
        capabilities: { commands: true, authoritativeState: false, toggles: false },
        cheats: [{ id: "health", label: "Health", state: "enabled", authoritative: true, operations: ["toggle"] }],
      }),
      controls({
        source: "cooperative",
        capabilities: { commands: true, authoritativeState: true, toggles: true },
        cheats: [{ id: "health", label: "Health", state: "unknown", authoritative: true, operations: ["toggle"] }],
      }),
      controls({
        source: "cooperative",
        capabilities: { commands: true, authoritativeState: true, toggles: true },
        cheats: [{ id: "health", label: "Health", state: "enabled", authoritative: true, operations: ["enable"] }],
      }),
    ];

    for (const value of cases) {
      const nodes = descendants(CheatControlList({ controls: value, busy: false, onCommand: vi.fn() }));
      expect(nodes.filter((node) => node.type === "ButtonItem")).toHaveLength(1);
      expect(nodes.some((node) => node.type === "ToggleField")).toBe(false);
      expect(nodes.map((node) => node.props?.description).join(" ")).toContain("Estado desconhecido");
    }
  });
});
