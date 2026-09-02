import { describe, expect, it, vi } from "vitest";

vi.hoisted(() => {
  vi.stubGlobal("window", {
    SP_REACT: {
      createElement: (type: unknown, props: Record<string, unknown> | null, ...children: unknown[]) => ({
        type,
        props: {
          ...props,
          children: children.length === 0 ? undefined : children.length === 1 ? children[0] : children,
        },
      }),
      Fragment: "Fragment",
    },
  });
});

vi.mock("react", () => ({
  useEffect: vi.fn(),
  useRef: <T>() => ({ current: null as T | null }),
  useState: <T>(initial: T) => [initial, vi.fn()],
}));

vi.mock("@decky/ui", () => {
  const component = (name: string) => name;
  return {
    ConfirmModal: component("ConfirmModal"),
    DialogButton: component("DialogButton"),
    Field: component("Field"),
    Focusable: component("Focusable"),
    showModal: vi.fn(),
  };
});

vi.mock("@decky/api", () => ({ callable: () => vi.fn(async () => undefined) }));

vi.mock("../src/infra/steamInput/adapter", () => ({
  createSteamInputLayoutAdapter: () => ({
    probe: vi.fn(async () => ({ status: "unavailable", diagnostic: "steam_input_method_unavailable" })),
    inspectSelectedLayout: vi.fn(),
    createSeparateLayout: vi.fn(),
    openConfigurator: vi.fn(),
  }),
}));

import { SteamInputRadialMenu } from "../src/components/SteamInputRadialMenu";

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

const textContent = (value: unknown): string => {
  if (Array.isArray(value)) return value.map(textContent).join("");
  if (typeof value === "string" || typeof value === "number") return String(value);
  if (!value || typeof value !== "object") return "";
  return textContent((value as ElementNode).props?.children);
};

const props = {
  appId: 123456789,
  identity: "gog:1482265668" as const,
  controls: {
    identity: "gog:1482265668" as const,
    status: "ready" as const,
    trainerSha256: "a".repeat(64),
    source: "manual" as const,
    trainerLabel: "Manual trainer",
    cheats: [{ id: "health", label: "Health", hotkey: { modifiers: [], key: "F1" }, state: "unknown" as const }],
    capabilities: { commands: true, authoritativeState: false, toggles: false },
    diagnostic: null,
  },
};

describe("Steam Input radial menu", () => {
  it("keeps the probe build read-only and offers safe export plus configurator fallback", () => {
    const nodes = descendants(SteamInputRadialMenu(props));
    const text = textContent(nodes);
    const rendered = nodes
      .flatMap((node) => [node.props?.label, node.props?.description])
      .filter((value): value is string => typeof value === "string")
      .join(" ");
    const buttons = nodes.filter((node) => node.type === "DialogButton");

    expect(rendered).toContain("Steam Input runtime not physically validated");
    expect(text).toContain("Export safe probe report");
    expect(text).toContain("Open Steam controller configurator");
    expect(buttons.some((node) => textContent(node).includes("Generate layout") && node.props?.disabled === true)).toBe(
      true,
    );
    expect(text).not.toContain("Quick Access");
  });
});
