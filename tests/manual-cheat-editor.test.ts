import { describe, expect, it, vi } from "vitest";

const draft = vi.hoisted(() => ({ value: "" as unknown, labelReads: 0 }));

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

vi.mock("react", () => ({
  useState: <T>(initial: T) => {
    draft.labelReads += 1;
    const value = (draft.labelReads === 1 && draft.value !== "" ? draft.value : initial) as T;
    return [
      value,
      (next: T) => {
        draft.value = next;
      },
    ] as const;
  },
}));

vi.mock("@decky/ui", () => {
  const component = (name: string) => name;
  return {
    ButtonItem: component("ButtonItem"),
    DialogButton: component("DialogButton"),
    DropdownItem: component("DropdownItem"),
    Field: component("Field"),
    TextField: component("TextField"),
  };
});

import { isManualCheatEditorAvailable, ManualCheatEditor } from "../src/components/ManualCheatEditor";

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

const hash = "a".repeat(64);

describe("ManualCheatEditor", () => {
  it("is available only for a ready response with a known trainer hash", () => {
    expect(isManualCheatEditorAvailable(true, hash)).toBe(true);
    expect(isManualCheatEditorAvailable(false, hash)).toBe(false);
    expect(isManualCheatEditorAvailable(true, "unknown")).toBe(false);
    expect(isManualCheatEditorAvailable(true, undefined)).toBe(false);
  });

  it("uses only finite native selectors and enforces the 80-character label limit", () => {
    const nodes = descendants(
      ManualCheatEditor({
        ready: true,
        trainerSha256: hash,
        busy: false,
        cheats: [],
        onAdd: vi.fn(),
        onRemove: vi.fn(),
      }),
    );
    const textField = nodes.find((node) => node.type === "TextField");
    const selectors = nodes.filter((node) => node.type === "DropdownItem");

    expect(textField?.props?.maxLength).toBe(80);
    expect(selectors).toHaveLength(2);
    expect(nodes.some((node) => node.props?.name === "vk")).toBe(false);
    expect(nodes.some((node) => node.props?.name === "command")).toBe(false);
    expect(nodes.some((node) => node.props?.name === "VK")).toBe(false);
    const keyOptions = selectors[0]?.props?.rgOptions as unknown[];
    expect(keyOptions.length).toBeGreaterThan(40);
    expect(selectors[1]?.props?.rgOptions).toHaveLength(8);
  });

  it("adds a normalized manual control and removes an existing one", async () => {
    const onAdd = vi.fn().mockResolvedValue(undefined);
    const onRemove = vi.fn().mockResolvedValue(undefined);
    draft.value = "Health cheat";
    draft.labelReads = 0;
    const nodes = descendants(
      ManualCheatEditor({
        ready: true,
        trainerSha256: hash,
        busy: false,
        cheats: [{ id: "old", label: "Old cheat", hotkey: { modifiers: [], key: "F2" }, state: "unknown" }],
        onAdd,
        onRemove,
      }),
    );
    const add = nodes.find((node) => node.type === "DialogButton");
    const remove = nodes.find((node) => node.type === "ButtonItem");

    expect(add).toBeDefined();
    expect(remove).toBeDefined();
    const onAddClick = add?.props?.onClick as () => Promise<void>;
    const onRemoveClick = remove?.props?.onClick as () => void;
    await onAddClick();
    onRemoveClick();

    expect(onAdd).toHaveBeenCalledWith("Health cheat", { modifiers: [], key: "A" });
    expect(onRemove).toHaveBeenCalledWith("old");
    draft.value = "";
    draft.labelReads = 0;
  });

  it("does not expose editor actions before readiness or for an unknown hash", () => {
    for (const props of [
      { ready: false, trainerSha256: hash },
      { ready: true, trainerSha256: "unknown" },
    ]) {
      const nodes = descendants(
        ManualCheatEditor({ ...props, busy: false, cheats: [], onAdd: vi.fn(), onRemove: vi.fn() }),
      );
      expect(nodes.some((node) => node.type === "TextField")).toBe(false);
      expect(nodes.some((node) => node.type === "DialogButton")).toBe(false);
    }
  });
});
