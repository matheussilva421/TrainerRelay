import { ButtonItem, Field, Focusable, ToggleField } from "@decky/ui";
import type { FC } from "react";
import { formatHotkey } from "../domain/cheats/decoder";
import type { CheatCommandResult, CheatDescriptor, ReadyCheatControls } from "../domain/cheats/types";

export interface CheatControlListProps {
  controls: ReadyCheatControls;
  busy: boolean;
  onCommand: (cheatId: string) => undefined | Promise<CheatCommandResult | undefined>;
  lastResults?: Record<string, string>;
}

const hasApplicableToggle = (controls: ReadyCheatControls, cheat: CheatDescriptor): boolean => {
  if (
    controls.source !== "cooperative" ||
    controls.capabilities.authoritativeState !== true ||
    controls.capabilities.toggles !== true ||
    cheat.authoritative !== true ||
    (cheat.state !== "enabled" && cheat.state !== "disabled")
  )
    return false;
  if (cheat.operations?.includes("toggle")) return true;
  if (cheat.state === "enabled") return cheat.operations?.includes("disable") === true;
  return cheat.operations?.includes("enable") === true;
};

const hotkeyText = (cheat: CheatDescriptor): string => {
  const hotkeys = cheat.hotkeys ?? (cheat.hotkey ? [cheat.hotkey] : []);
  return hotkeys.map(formatHotkey).join(" / ");
};

const commandDescription = (cheat: CheatDescriptor, lastResult?: string, showState = false): string => {
  const hotkey = hotkeyText(cheat);
  const status =
    lastResult ?? (showState && cheat.state !== "unknown" ? `Estado: ${cheat.state}` : "Estado desconhecido");
  return hotkey ? `${hotkey} · ${status}` : status;
};

export const CheatControlList: FC<CheatControlListProps> = ({ controls, busy, onCommand, lastResults = {} }) => (
  <Focusable style={{ display: "flex", flexDirection: "column" }}>
    <Field
      label="Cheat controls"
      description={`${controls.trainerLabel} · SHA-256 ${controls.trainerSha256.slice(0, 12)}…`}
      padding="standard"
      bottomSeparator="standard"
    />
    {controls.cheats.map((cheat) => {
      const onActivate = () => onCommand(cheat.id);
      const toggleAvailable = hasApplicableToggle(controls, cheat);
      const description = commandDescription(cheat, lastResults[cheat.id], toggleAvailable);
      if (toggleAvailable) {
        return (
          <ToggleField
            key={cheat.id}
            label={cheat.label}
            description={description}
            checked={cheat.state === "enabled"}
            disabled={busy}
            onChange={() => void onActivate()}
            highlightOnFocus
            bottomSeparator="standard"
          />
        );
      }
      const itemProps = {
        key: cheat.id,
        label: cheat.label,
        description,
        disabled: busy || controls.capabilities.commands !== true,
        onClick: onActivate,
        onActivate,
        highlightOnFocus: true,
        bottomSeparator: "standard" as const,
      };
      return <ButtonItem {...itemProps} />;
    })}
  </Focusable>
);
