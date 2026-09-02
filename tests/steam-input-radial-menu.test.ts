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

const hookMock = vi.hoisted(() => ({
  controller: {
    state: {
      status: "ready" as const,
      reason: "Steam Input runtime not physically validated",
      busy: false,
      generationAvailable: false,
      plan: {} as never,
      commandCount: 1,
      pageCount: 1,
      skippedCount: 0,
      skippedReasons: [] as readonly string[],
    },
    prepare: vi.fn(),
    beginConfirmation: vi.fn(async () => ({ status: "confirming" as const })),
    confirm: vi.fn(async () => ({ status: "ready" as const })),
    exportSafeProbe: vi.fn(async () => ({ path: "/home/deck/Downloads/probe.json", bytesWritten: 10 })),
    openConfigurator: vi.fn(async () => undefined),
  },
}));

vi.mock("../src/hooks/useSteamInputRadialMenu", () => ({
  useSteamInputRadialMenu: () => hookMock.controller,
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

import { showModal } from "@decky/ui";
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

  it("describes the actual readonly confirmation action and disables every action while busy", async () => {
    hookMock.controller.state.busy = false;
    const nodes = descendants(SteamInputRadialMenu(props));
    const prepareButton = nodes.find(
      (node) => node.type === "DialogButton" && textContent(node).includes("Prepare Steam Input radial menu"),
    );

    (prepareButton?.props?.onClick as (() => void) | undefined)?.();
    await vi.waitFor(() => expect(showModal).toHaveBeenCalled());
    const modalCalls = vi.mocked(showModal).mock.calls;
    const modal = modalCalls[modalCalls.length - 1]?.[0] as ElementNode;
    expect(modal.props?.strTitle).toBe("Confirm read-only Steam Input preview?");
    expect(modal.props?.strDescription).toContain("No Steam layout will be generated or selected");
    expect(modal.props?.strOKButtonText).toBe("Confirm preview");
    expect(String(modal.props?.strOKButtonText)).not.toContain("export");
    (modal.props?.onOK as (() => void) | undefined)?.();
    expect(hookMock.controller.confirm).toHaveBeenCalled();

    hookMock.controller.state.busy = true;
    const busyButtons = descendants(SteamInputRadialMenu(props)).filter((node) => node.type === "DialogButton");
    expect(busyButtons).toHaveLength(4);
    expect(busyButtons.every((button) => button.props?.disabled === true)).toBe(true);
    hookMock.controller.state.busy = false;
  });
});
