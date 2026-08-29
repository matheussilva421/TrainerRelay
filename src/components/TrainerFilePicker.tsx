import { DialogButton, Field, Focusable, TextField } from "@decky/ui";
import { type CSSProperties, type FC, useEffect, useLayoutEffect, useRef, useState } from "react";
import { FaFolderOpen } from "react-icons/fa6";
import { logger } from "../utils/logger";

interface TrainerFilePickerProps {
  disabled?: boolean;
  value: string;
  onBrowse: () => void;
}

const BROWSE_BUTTON_WIDTH = 40;
const ROW_GAP = 8;

const rowStyle = {
  display: "flex",
  width: "100%",
  gap: `${ROW_GAP}px`,
} satisfies CSSProperties;

const browseButtonStyle = {
  alignItems: "center",
  display: "flex",
  justifyContent: "center",
  flex: "0 0 auto",
  minWidth: "auto",
  width: `${BROWSE_BUTTON_WIDTH}px`,
  padding: "10px",
} satisfies CSSProperties;

export const TrainerFilePicker: FC<TrainerFilePickerProps> = ({ disabled, value, onBrowse }) => {
  const rowRef = useRef<HTMLDivElement>(null);
  const [pathWidth, setPathWidth] = useState<number | undefined>(undefined);

  const measure = () => {
    const row = rowRef.current;
    if (!row) return;
    const available = row.clientWidth - BROWSE_BUTTON_WIDTH - ROW_GAP;
    setPathWidth(available > 0 ? available : undefined);
  };

  useLayoutEffect(measure, []);

  useEffect(() => {
    const row = rowRef.current;
    if (!row) return;
    const observer = new ResizeObserver(measure);
    observer.observe(row);
    return () => observer.disconnect();
  }, []);

  const pathStyle = {
    fontSize: "14px",
    padding: "10px",
    width: pathWidth === undefined ? "100%" : `${pathWidth}px`,
    minWidth: 0,
    boxSizing: "border-box",
  } satisfies CSSProperties;

  const handleBrowse = () => {
    logger.info("[TrainerRelay:picker] ui-activated", { disabled: Boolean(disabled) });
    onBrowse();
  };

  return (
    <Focusable style={{ boxShadow: "none", marginTop: "-4px" }}>
      <Field
        label="Trainer executable"
        description="Use the folder button to browse the Deck and select one absolute .exe file."
        padding="standard"
        bottomSeparator="standard"
        childrenLayout="below"
      >
        <Focusable style={rowStyle} ref={rowRef}>
          <TextField style={pathStyle} disabled={true} value={value} />
          <DialogButton disabled={disabled} onClick={handleBrowse} style={browseButtonStyle}>
            <FaFolderOpen />
          </DialogButton>
        </Focusable>
      </Field>
    </Focusable>
  );
};
