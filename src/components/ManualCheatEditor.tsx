import { ButtonItem, DialogButton, DropdownItem, Field, TextField } from "@decky/ui";
import type { ComponentProps, FC } from "react";
import { useState } from "react";
import type { CheatDescriptor, HotkeyModifier, SymbolicHotkey } from "../domain/cheats/types";

export const MANUAL_CHEAT_KEYS = [
  ...Array.from({ length: 26 }, (_, index) => String.fromCharCode(65 + index)),
  ...Array.from({ length: 10 }, (_, index) => String(index)),
  ...Array.from({ length: 24 }, (_, index) => `F${index + 1}`),
  ...Array.from({ length: 10 }, (_, index) => `NUMPAD${index}`),
  "MULTIPLY",
  "ADD",
  "SUBTRACT",
  "DECIMAL",
  "DIVIDE",
  "INSERT",
  "DELETE",
  "HOME",
  "END",
  "PAGEUP",
  "PAGEDOWN",
  "UP",
  "DOWN",
  "LEFT",
  "RIGHT",
  "SPACE",
  "TAB",
  "ENTER",
  "BACKSPACE",
  "PAUSE",
  "CAPSLOCK",
  "SCROLLLOCK",
  "NUMLOCK",
] as const;

export const MANUAL_CHEAT_MODIFIERS: readonly { data: string; label: string }[] = [
  { data: "", label: "None" },
  { data: "ctrl", label: "Ctrl" },
  { data: "alt", label: "Alt" },
  { data: "shift", label: "Shift" },
  { data: "ctrl+alt", label: "Ctrl + Alt" },
  { data: "ctrl+shift", label: "Ctrl + Shift" },
  { data: "alt+shift", label: "Alt + Shift" },
  { data: "ctrl+alt+shift", label: "Ctrl + Alt + Shift" },
];

const LimitedTextField = TextField as FC<ComponentProps<typeof TextField> & { maxLength?: number }>;

const hashPattern = /^[0-9a-f]{64}$/;

export const isManualCheatEditorAvailable = (ready: boolean, trainerSha256: string | undefined): boolean =>
  ready && trainerSha256 !== undefined && hashPattern.test(trainerSha256);

export interface ManualCheatEditorProps {
  ready: boolean;
  trainerSha256: string | undefined;
  busy: boolean;
  cheats: CheatDescriptor[];
  onAdd: (label: string, hotkey: SymbolicHotkey) => undefined | Promise<unknown>;
  onRemove: (cheatId: string) => undefined | Promise<unknown>;
}

const modifiersFromData = (data: string): HotkeyModifier[] =>
  data
    .split("+")
    .filter(
      (modifier): modifier is HotkeyModifier => modifier === "ctrl" || modifier === "alt" || modifier === "shift",
    );

export const ManualCheatEditor: FC<ManualCheatEditorProps> = ({
  ready,
  trainerSha256,
  busy,
  cheats,
  onAdd,
  onRemove,
}) => {
  const available = isManualCheatEditorAvailable(ready, trainerSha256);
  const [label, setLabel] = useState("");
  const [key, setKey] = useState<string>(MANUAL_CHEAT_KEYS[0]);
  const [modifierData, setModifierData] = useState("");

  if (!available) {
    return (
      <Field
        label="Manual controls"
        description="Manual controls are available after the trainer response is ready."
        padding="standard"
      />
    );
  }

  const normalizedLabel = label.trim();
  const canAdd = normalizedLabel.length >= 1 && normalizedLabel.length <= 80 && !busy;
  const add = async () => {
    if (!canAdd) return;
    await onAdd(normalizedLabel, { key, modifiers: modifiersFromData(modifierData) });
    setLabel("");
  };

  return (
    <Field
      label="Manual controls"
      description="Add a label and choose a finite symbolic hotkey."
      padding="standard"
      childrenLayout="below"
    >
      <LimitedTextField
        label="Name"
        value={label}
        maxLength={80}
        disabled={busy}
        onChange={(event) => setLabel(event.currentTarget.value)}
      />
      <DropdownItem
        label="Key"
        rgOptions={MANUAL_CHEAT_KEYS.map((value) => ({ data: value, label: value }))}
        selectedOption={key}
        disabled={busy}
        onChange={(option) => setKey(String(option.data))}
      />
      <DropdownItem
        label="Modifiers"
        rgOptions={[...MANUAL_CHEAT_MODIFIERS]}
        selectedOption={modifierData}
        disabled={busy}
        onChange={(option) => setModifierData(String(option.data))}
      />
      <DialogButton disabled={!canAdd} onClick={() => void add()}>
        Add manual cheat
      </DialogButton>
      {cheats.map((cheat) => (
        <ButtonItem
          key={cheat.id}
          label={`Remove ${cheat.label}`}
          disabled={busy}
          onClick={() => void onRemove(cheat.id)}
        />
      ))}
    </Field>
  );
};
