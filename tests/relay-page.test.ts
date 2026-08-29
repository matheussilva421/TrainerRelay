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

const controller = vi.hoisted(() => ({
  model: {
    kind: "supported" as const,
    heading: "Trainer Relay",
    identity: "gog:1482265568" as const,
    migration: { status: "none" as const },
    status: { state: "disabled" as const, diagnostic: null },
    controls: { retry: false },
  },
  configState: { status: "ready" as const, value: { schemaVersion: 1 as const, games: {} } },
  currentConfig: { enabled: false, trainerPath: "" },
  busy: false,
  migrationBusy: false,
  migrationMessage: undefined,
  trainerDraft: "",
  setTrainerDraft: vi.fn(),
  prefixDraft: "",
  setPrefixDraft: vi.fn(),
  chooseTrainer: vi.fn(),
  saveTrainer: vi.fn(),
  toggleRelay: vi.fn(),
  savePrefix: vi.fn(),
  retry: vi.fn(),
  migrate: vi.fn(),
}));

vi.mock("../src/hooks/useRelayPageController", () => ({
  useRelayPageController: () => controller,
}));

vi.mock("@decky/ui", () => {
  const component = (name: string) => name;
  return {
    ConfirmModal: component("ConfirmModal"),
    DialogButton: component("DialogButton"),
    Field: component("Field"),
    Focusable: component("Focusable"),
    Navigation: { CloseSideMenus: vi.fn(), NavigateToExternalWeb: vi.fn() },
    PanelSection: component("PanelSection"),
    PanelSectionRow: component("PanelSectionRow"),
    showModal: vi.fn(),
    TextField: component("TextField"),
    ToggleField: component("ToggleField"),
  };
});

vi.mock("react-icons/fa6", () => ({
  FaArrowsRotate: "FaArrowsRotate",
  FaFolderOpen: "FaFolderOpen",
  FaShieldHalved: "FaShieldHalved",
}));

import RelayPage from "../src/views/RelayPage";

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

describe("Trainer Relay page", () => {
  it("keeps manual trainer path configuration available when the Decky picker cannot be used", () => {
    const nodes = descendants(RelayPage({ appid: 48_226_5568 }));

    expect(
      nodes.some(
        (node) =>
          node.type === "TextField" &&
          node.props?.value === "" &&
          node.props?.disabled === false &&
          node.props?.onChange instanceof Function,
      ),
    ).toBe(true);
    expect(
      nodes.some(
        (node) =>
          node.type === "DialogButton" &&
          node.props?.children === "Save trainer path" &&
          node.props?.onClick instanceof Function,
      ),
    ).toBe(true);
  });
});
