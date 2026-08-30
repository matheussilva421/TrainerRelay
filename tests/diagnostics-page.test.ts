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

const controller = vi.hoisted(() => ({
  state: "ready" as const,
  response: {
    settings: { schemaVersion: 1 as const, enabled: true },
    bytesUsed: 1_048_576,
    byteLimit: 52_428_800 as const,
    eventCount: 22,
    storageDiagnostic: null as string | null,
    lastExportPath: "/home/deck/Downloads/TrainerRelay-diagnostics.txt" as string | null,
  },
  events: Array.from({ length: 22 }, (_, index) => ({
    sequence: index + 1,
    timestamp: "2026-08-30T12:00:00.000Z",
    category: "process" as const,
    event: "candidate_rejected",
    outcome: "rejected" as const,
    details: { reason: `reason_${index + 1}` },
  })),
  busy: null as "toggle" | "export" | "clear" | null,
  toggle: vi.fn(),
  exportText: vi.fn(),
  requestClear: vi.fn(),
  clearConfirmed: vi.fn(),
}));

const showModal = vi.hoisted(() => vi.fn());
vi.mock("@decky/ui", () => ({
  ConfirmModal: "ConfirmModal",
  DialogButton: "DialogButton",
  Field: "Field",
  Focusable: "Focusable",
  showModal,
  ToggleField: "ToggleField",
}));
vi.mock("react-icons/fa6", () => ({ FaFileExport: "FaFileExport", FaTrash: "FaTrash" }));
vi.mock("../src/hooks/useDiagnosticsController", () => ({ useDiagnosticsController: () => controller }));

import { createDiagnosticsActions } from "../src/hooks/diagnosticsActions";
import DiagnosticsPage from "../src/views/DiagnosticsPage";

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
  if (Array.isArray(value)) return value.map(textContent).join(" ");
  if (typeof value === "string" || typeof value === "number") return String(value);
  if (!value || typeof value !== "object") return "";
  const node = value as ElementNode;
  return [node.props?.label, node.props?.description, textContent(node.props?.children)].filter(Boolean).join(" ");
};

const invoke = (value: unknown): void => {
  if (typeof value !== "function") throw new TypeError("expected action");
  value();
};

describe("Diagnostics page", () => {
  it("shows persistent state, exact capacity, export path, storage state, and only the latest 20 events", () => {
    const nodes = descendants(DiagnosticsPage({}));
    const fields = nodes.filter((node) => node.type === "Field");
    const eventLabels = fields.map((node) => node.props?.label).filter((label) => String(label).startsWith("#"));
    expect(nodes.find((node) => node.type === "ToggleField")?.props?.checked).toBe(true);
    expect(textContent(nodes)).toContain("1048576 / 52428800 bytes");
    expect(textContent(nodes)).toContain("/home/deck/Downloads/TrainerRelay-diagnostics.txt");
    expect(eventLabels).toHaveLength(20);
    expect(eventLabels[0]).toContain("#3");
    expect(eventLabels[19]).toContain("#22");
  });

  it("keeps direct controls focusable, confirms clear, and disables actions after an RPC error", () => {
    const nodes = descendants(DiagnosticsPage({}));
    const buttons = nodes.filter((node) => node.type === "DialogButton");
    invoke(buttons.find((node) => node.props?.children?.toString().includes("Clear"))?.props?.onClick);
    expect(controller.requestClear).toHaveBeenCalledOnce();
    expect(showModal).toHaveBeenCalledOnce();
    const modal = showModal.mock.calls[0][0] as ElementNode;
    expect(modal.type).toBe("ConfirmModal");
    invoke(modal.props?.onOK);
    expect(controller.clearConfirmed).toHaveBeenCalledOnce();

    const previous = controller.state;
    Object.assign(controller, { state: "error" });
    try {
      const failed = descendants(DiagnosticsPage({}));
      expect(failed.filter((node) => node.type === "DialogButton").every((node) => node.props?.disabled === true)).toBe(
        true,
      );
      expect(failed.find((node) => node.type === "ToggleField")?.props?.disabled).toBe(true);
    } finally {
      Object.assign(controller, { state: previous });
    }
  });

  it("retains disabled history, renders empty/storage states, and never renders raw HTML", () => {
    const previousEvents = controller.events;
    const previousEnabled = controller.response.settings.enabled;
    const previousStorage = controller.response.storageDiagnostic;
    controller.response.settings.enabled = false;
    controller.response.storageDiagnostic = "diagnostic_storage_unavailable";
    controller.events = [];
    try {
      const nodes = descendants(DiagnosticsPage({}));
      expect(textContent(nodes)).toContain("No diagnostic events recorded yet");
      expect(textContent(nodes)).toContain("diagnostic_storage_unavailable");
      expect(nodes.every((node) => node.props?.dangerouslySetInnerHTML === undefined)).toBe(true);
    } finally {
      controller.events = previousEvents;
      controller.response.settings.enabled = previousEnabled;
      controller.response.storageDiagnostic = previousStorage;
    }
  });

  it("persists toggle, reports export path/failure, and clears local history after backend confirmation", async () => {
    const response = controller.response;
    const rpc = {
      setDiagnosticsEnabled: vi.fn().mockResolvedValue(response),
      exportDiagnostics: vi.fn().mockResolvedValue({ path: "/home/deck/Downloads/new.txt", bytesWritten: 42 }),
      getDiagnosticSettings: vi.fn().mockResolvedValue(response),
      clearDiagnostics: vi.fn().mockResolvedValue({ ...response, generation: 2 }),
    };
    const updateResponse = vi.fn();
    const updateEvents = vi.fn();
    const notice = vi.fn();
    const setBusy = vi.fn();
    const actions = createDiagnosticsActions({ rpc, updateResponse, updateEvents, notice, setBusy });

    await actions.toggle(false);
    await actions.exportText();
    await actions.clearConfirmed();
    expect(rpc.setDiagnosticsEnabled).toHaveBeenCalledWith(false);
    expect(notice).toHaveBeenCalledWith("Diagnostics exported to /home/deck/Downloads/new.txt");
    expect(updateEvents).toHaveBeenCalledWith([]);

    rpc.exportDiagnostics.mockRejectedValueOnce(new Error("private path"));
    await actions.exportText();
    expect(notice).toHaveBeenCalledWith("Diagnostic export failed. Existing logs were preserved.");
    expect(JSON.stringify(notice.mock.calls)).not.toContain("private path");
  });
});
