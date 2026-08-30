import { ButtonItem } from "@decky/ui";
import type { FC } from "react";
import { FaFolderOpen } from "react-icons/fa6";
import { logger } from "../utils/logger";

interface TrainerFilePickerProps {
  disabled?: boolean;
  value: string;
  onBrowse: () => void;
}

export const TrainerFilePicker: FC<TrainerFilePickerProps> = ({ disabled, value, onBrowse }) => {
  const handleBrowse = () => {
    logger.info("[TrainerRelay:picker] ui-activated", { disabled: Boolean(disabled) });
    onBrowse();
  };

  return (
    <ButtonItem
      label="Trainer executable"
      description={value || "Press A to browse the Deck and select one absolute .exe file."}
      disabled={disabled}
      onClick={handleBrowse}
      highlightOnFocus
      bottomSeparator="standard"
    >
      <FaFolderOpen />
    </ButtonItem>
  );
};
