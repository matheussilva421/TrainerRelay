import { ConfirmModal, DialogButton, Field, Focusable, showModal, ToggleField } from "@decky/ui";
import type { FC } from "react";
import { FaFileExport, FaTrash } from "react-icons/fa6";

import type { DiagnosticDetailValue, DiagnosticEvent } from "../domain/diagnostics/types";
import { useDiagnosticsController } from "../hooks/useDiagnosticsController";

const displayValue = (value: DiagnosticDetailValue): string => {
  const text = typeof value === "string" ? value : JSON.stringify(value);
  return text.length > 256 ? `${text.slice(0, 253)}...` : text;
};

const eventDescription = (event: DiagnosticEvent): string => {
  const context = [
    event.identity ? `identity=${event.identity}` : "",
    event.session ? `pid=${event.session.pid} startTime=${event.session.startTime}` : "",
    ...Object.keys(event.details)
      .sort()
      .map((key) => `${key}=${displayValue(event.details[key])}`),
  ].filter(Boolean);
  return context.length > 0 ? context.join(" ") : "No event details.";
};

const DiagnosticsPage: FC = () => {
  const controller = useDiagnosticsController();
  const { state, response, events, busy, toggle, exportText, requestClear, clearConfirmed } = controller;
  const latestEvents = events.slice(-20);
  const controlsDisabled = state !== "ready" || busy !== null;

  const confirmClear = () => {
    requestClear();
    showModal(
      <ConfirmModal
        strTitle="Clear Trainer Relay diagnostic journal?"
        strDescription="This removes only Trainer Relay's rotating NDJSON journal. Exported TXT files remain in Downloads."
        strOKButtonText="Clear logs"
        strCancelButtonText="Cancel"
        onCancel={() => controller.cancelClear?.()}
        onOK={() => void clearConfirmed()}
        bOKDisabled={busy !== null}
      />,
      window,
    );
  };

  return (
    <Focusable style={{ display: "flex", flexDirection: "column" }}>
      <ToggleField
        label="Persistent diagnostic mode"
        description="Stays enabled until you turn it off. Records sanitized Trainer Relay decisions only."
        checked={response.settings.enabled}
        disabled={controlsDisabled}
        onChange={(enabled) => void toggle(enabled)}
        bottomSeparator="standard"
        highlightOnFocus
      />
      <Field
        label={state === "loading" ? "Loading diagnostics" : state === "error" ? "Diagnostics unavailable" : "Storage"}
        description={`${response.bytesUsed} / ${response.byteLimit} bytes · ${response.eventCount} persisted events`}
        padding="standard"
        bottomSeparator="standard"
      />
      {response.storageDiagnostic && (
        <Field
          label="Storage warning"
          description={response.storageDiagnostic}
          padding="standard"
          bottomSeparator="standard"
        />
      )}
      <Field
        label="Last TXT export"
        description={response.lastExportPath ?? "No TXT export created yet."}
        padding="standard"
        bottomSeparator="standard"
      />
      <Field padding="standard" childrenLayout="below" bottomSeparator="standard">
        <DialogButton disabled={controlsDisabled} onClick={() => void exportText()}>
          <FaFileExport /> Export TXT to Downloads
        </DialogButton>
        <DialogButton disabled={controlsDisabled} onClick={confirmClear}>
          <FaTrash /> Clear logs
        </DialogButton>
      </Field>
      <Field
        label="Latest 20 events"
        description={latestEvents.length === 0 ? "No diagnostic events recorded yet." : "Oldest to newest."}
        padding="standard"
        bottomSeparator="standard"
      />
      {latestEvents.map((event) => (
        <Field
          key={`${event.sequence}-${event.timestamp}`}
          label={`#${event.sequence} ${event.timestamp} · ${event.category}/${event.event} · ${event.outcome}`}
          description={eventDescription(event)}
          padding="standard"
          bottomSeparator="standard"
        />
      ))}
    </Focusable>
  );
};

export default DiagnosticsPage;
