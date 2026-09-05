import { afterEach, describe, expect, it, vi } from "vitest";

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
  useLayoutEffect: (effect: () => void) => effect(),
  useRef: <T>() => ({ current: null as T | null }),
  useState: <T>(initial: T) => [initial, vi.fn()],
}));

const controller = vi.hoisted(() => ({
  model: {
    kind: "supported" as const,
    heading: "Trainer Relay" as const,
    identity: "gog:1482265568" as const,
    migration: { status: "none" as const },
    status: { state: "disabled" as const, diagnosticCode: null },
    controls: { browse: true, enable: false, retry: false },
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

const cheatControls = vi.hoisted(() => ({
  response: undefined as unknown,
  status: "unavailable" as const,
  error: null as string | null,
  busy: false,
  lastResults: {} as Record<string, string>,
  refresh: vi.fn(),
  sendCommand: vi.fn(),
  addManualCheatControl: vi.fn(),
  removeManualCheatControl: vi.fn(),
}));

vi.mock("../src/hooks/useRelayPageController", () => ({
  useRelayPageController: () => controller,
}));

vi.mock("../src/hooks/useCheatControls", () => ({
  useCheatControls: () => cheatControls,
}));

vi.mock("@decky/ui", () => {
  const component = (name: string) => name;
  return {
    ButtonItem: component("ButtonItem"),
    ConfirmModal: component("ConfirmModal"),
    DialogButton: component("DialogButton"),
    DropdownItem: component("DropdownItem"),
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

import { CheatControlList } from "../src/components/CheatControlList";
import { ManualCheatEditor } from "../src/components/ManualCheatEditor";
import { TrainerFilePicker } from "../src/components/TrainerFilePicker";
import type { TrainerRelayViewModel } from "../src/domain/relay/viewModel";
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

const textContent = (value: unknown): string => {
  if (Array.isArray(value)) return value.map(textContent).join("");
  if (typeof value === "string" || typeof value === "number") return String(value);
  if (!value || typeof value !== "object") return "";
  return textContent((value as ElementNode).props?.children);
};

describe("Trainer Relay page", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("uses one native action row for the trainer picker without a manual path action", () => {
    const onBrowse = vi.fn();
    const nodes = descendants(TrainerFilePicker({ disabled: false, value: "", onBrowse }));

    expect(nodes.some((node) => node.type === "TextField")).toBe(false);
    expect(nodes.filter((node) => node.type === "ButtonItem")).toHaveLength(1);
    expect(textContent(RelayPage({ appid: 48_226_5568 }))).not.toContain("Save trainer path");
  });

  it("keeps the native action enabled and delegates its activation to Decky", () => {
    const consoleInfo = vi.spyOn(console, "info").mockImplementation(() => undefined);
    const onBrowse = vi.fn();
    const nodes = descendants(TrainerFilePicker({ disabled: false, value: "", onBrowse }));
    const browseButton = nodes.find((node) => node.type === "ButtonItem");

    expect(browseButton?.props?.disabled).toBe(false);
    if (browseButton?.props?.disabled !== true) {
      (browseButton?.props?.onClick as (() => void) | undefined)?.();
    }

    expect(consoleInfo).toHaveBeenCalledWith(
      expect.stringContaining("Trainer Relay"),
      expect.any(String),
      "[TrainerRelay:picker] ui-activated",
      { disabled: false },
    );
    expect(onBrowse).toHaveBeenCalledOnce();
  });

  it("mounts the trainer picker directly in the page focus column like CheatDeck", () => {
    const page = RelayPage({ appid: 48_226_5568 }) as ElementNode;
    const children = page.props?.children;
    const directChildren: ElementNode[] = (Array.isArray(children) ? children : [children]).filter(
      (child): child is ElementNode => Boolean(child) && typeof child === "object",
    );

    expect(directChildren.some((child) => child?.type === TrainerFilePicker)).toBe(true);
  });

  it("keeps routed controls out of Quick Access PanelSection wrappers", () => {
    const page = RelayPage({ appid: 48_226_5568 }) as ElementNode;
    const nodes = descendants(page);

    expect(page?.type).toBe("Focusable");
    expect(nodes.some((node) => node.type === "PanelSection" || node.type === "PanelSectionRow")).toBe(false);
  });

  it("receives the safe identity and renders the routed cheat controls", () => {
    const previousResponse = cheatControls.response;
    const previousStatus = cheatControls.status;
    cheatControls.response = {
      identity: "gog:1482265568",
      status: "ready",
      trainerSha256: "a".repeat(64),
      source: "manual",
      trainerLabel: "Manual trainer",
      cheats: [{ id: "health", label: "Health", hotkey: { modifiers: [], key: "F1" }, state: "unknown" }],
      capabilities: { commands: true, authoritativeState: false, toggles: false },
      diagnostic: null,
    };
    (cheatControls as { status: string }).status = "ready";

    try {
      const nodes = descendants(RelayPage({ appid: 48_226_5568 }));
      expect(nodes.some((node) => node.type === CheatControlList)).toBe(true);
      expect(nodes.some((node) => node.type === ManualCheatEditor)).toBe(true);
    } finally {
      cheatControls.response = previousResponse;
      (cheatControls as { status: string }).status = previousStatus;
    }
  });

  it("renders no actionable controls for an unsupported shortcut", () => {
    const previousModel: TrainerRelayViewModel = controller.model;
    const unsupportedModel: TrainerRelayViewModel = {
      kind: "unsupported",
      heading: "Trainer Relay",
      message: "This shortcut is not a recognised UniFiDeck Epic/GOG launch.",
      repositoryUrl: "https://github.com/matheussilva421/TrainerRelay",
    };
    Object.assign(controller, { model: unsupportedModel });

    try {
      const nodes = descendants(RelayPage({ appid: 123 }));
      expect(nodes.some((node) => node.type === "DialogButton" || node.type === "ButtonItem")).toBe(false);
    } finally {
      Object.assign(controller, { model: previousModel });
    }
  });

  it("allows safe manual configuration while blocked legacy options keep enablement disabled", () => {
    const previousMigration = controller.model.migration;
    const previousControls = controller.model.controls;
    const previousTrainerPath = controller.currentConfig.trainerPath;
    (controller.model as { migration: { status: string } }).migration = { status: "blocked" };
    (controller.model as { controls: { browse: boolean; enable: boolean; retry: boolean } }).controls = {
      browse: true,
      enable: false,
      retry: false,
    };
    controller.currentConfig.trainerPath = "/home/deck/trainer.exe";

    try {
      const nodes = descendants(RelayPage({ appid: 48_226_5568 }));
      const picker = nodes.find((node) => node.type === TrainerFilePicker);
      const prefixInput = nodes.find((node) => node.type === "TextField");
      const enableToggle = nodes.find((node) => node.type === "ToggleField");

      expect(picker?.props?.disabled).toBe(false);
      expect(prefixInput?.props?.disabled).toBe(false);
      expect(enableToggle?.props?.disabled).toBe(true);
    } finally {
      controller.model.migration = previousMigration;
      controller.model.controls = previousControls;
      controller.currentConfig.trainerPath = previousTrainerPath;
    }
  });

  it("explains the required UMU container preparation without calling it a legacy repair", () => {
    const previousMigration = controller.model.migration;
    const previousTrainerPath = controller.currentConfig.trainerPath;
    (controller.model as { migration: unknown }).migration = {
      status: "ready",
      trainerPath: "/home/deck/trainer.exe",
      launchOptions: "UMU_CONTAINER_NSENTER=1 %command% gog:1482265568",
      changes: "container",
    };
    controller.currentConfig.trainerPath = "/home/deck/trainer.exe";

    try {
      const text = textContent(RelayPage({ appid: 48_226_5568 }));
      expect(text).toContain("Prepare UMU container re-entry");
      expect(text).not.toContain("incomplete or unsafe");
    } finally {
      controller.model.migration = previousMigration;
      controller.currentConfig.trainerPath = previousTrainerPath;
    }
  });
});
