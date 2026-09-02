import { ConfirmModal, DialogButton, Field, Focusable, showModal } from "@decky/ui";
import type { FC } from "react";
import type { ReadyCheatControls } from "../domain/cheats/types";
import type { Sha256Digest, SteamInputLayoutAdapter } from "../domain/steamInput/types";
import { type SteamInputRadialMenuRpc, useSteamInputRadialMenu } from "../hooks/useSteamInputRadialMenu";
import { sendNotice } from "../infra/decky";
import { radialLayoutRpc } from "../infra/radialLayoutRpc";
import { createSteamInputLayoutAdapter } from "../infra/steamInput/adapter";

export interface SteamInputRadialMenuProps {
  appId: number;
  identity: ReadyCheatControls["identity"];
  controls: ReadyCheatControls;
  adapter?: SteamInputLayoutAdapter;
  rpc?: SteamInputRadialMenuRpc;
  digest?: Sha256Digest;
}

const browserDigest: Sha256Digest = async (value) => {
  if (!globalThis.crypto?.subtle) throw new Error("digest_unavailable");
  return new Uint8Array(await globalThis.crypto.subtle.digest("SHA-256", value as unknown as BufferSource));
};

const defaultAdapter = (): SteamInputLayoutAdapter => {
  const globals = globalThis as typeof globalThis & {
    SteamClient?: { Input?: unknown; Apps?: unknown };
  };
  return createSteamInputLayoutAdapter({
    input: globals.SteamClient?.Input ?? {},
    app: globals.SteamClient?.Apps ?? {},
    digest: browserDigest,
  });
};

const SteamInputRadialMenu: FC<SteamInputRadialMenuProps> = (props) => {
  const controller = useSteamInputRadialMenu({
    appId: props.appId,
    identity: props.identity,
    controls: props.controls,
    adapter: props.adapter ?? defaultAdapter(),
    rpc: props.rpc ?? radialLayoutRpc,
    digest: props.digest ?? browserDigest,
  });
  const { state } = controller;

  const openConfirmation = async () => {
    const next = await controller.beginConfirmation();
    if (next.status !== "confirming") return;
    const modalWindow = (globalThis as typeof globalThis & { window?: Window }).window;
    if (!modalWindow) return;
    showModal(
      <ConfirmModal
        strTitle="Confirm read-only Steam Input preview?"
        strDescription={`No Steam layout will be generated or selected. This confirms a read-only preview of ${state.commandCount} command item(s) across ${state.pageCount} page(s). Physical click activates a selected item; touch release sends nothing.`}
        strOKButtonText="Confirm preview"
        strCancelButtonText="Cancel"
        onCancel={() => undefined}
        onOK={() => void controller.confirm()}
        bOKDisabled={state.busy}
      />,
      modalWindow,
    );
  };

  const exportProbe = async () => {
    try {
      const result = await controller.exportSafeProbe();
      if (result) sendNotice(`Safe probe report exported (${result.bytesWritten} bytes).`);
    } catch {
      sendNotice("Safe probe report could not be exported.");
    }
  };

  const openConfigurator = async () => {
    try {
      await controller.openConfigurator();
      sendNotice("Steam controller configurator opened.");
    } catch {
      sendNotice("Steam controller configurator is unavailable.");
    }
  };

  const summary =
    state.status === "unavailable"
      ? `Steam Input probe unavailable (${state.reason}).`
      : state.plan
        ? `${state.commandCount} command item(s) across ${state.pageCount} page(s).`
        : "Steam Input preview is ready to probe.";
  const skipped = state.skippedCount
    ? `Skipped controls: ${state.skippedCount}. ${state.skippedReasons.join("; ")}.`
    : "Skipped controls: 0.";

  return (
    <Focusable style={{ display: "flex", flexDirection: "column" }}>
      <Field
        label="Steam Input radial menu"
        description={`${summary} ${skipped} Left trackpad, physical click only.`}
        padding="standard"
        bottomSeparator="standard"
      >
        <DialogButton
          disabled={state.busy || state.status !== "ready" || !state.plan}
          onClick={() => void openConfirmation()}
        >
          Prepare Steam Input radial menu
        </DialogButton>
      </Field>
      <Field
        label="Generated layout"
        description="Steam Input runtime not physically validated"
        padding="standard"
        childrenLayout="below"
        bottomSeparator="standard"
      >
        <DialogButton disabled={state.busy || !state.generationAvailable}>Generate layout</DialogButton>
      </Field>
      <Field padding="standard" childrenLayout="below" bottomSeparator="standard">
        <DialogButton disabled={state.busy} onClick={() => void exportProbe()}>
          Export safe probe report
        </DialogButton>
        <DialogButton disabled={state.busy} onClick={() => void openConfigurator()}>
          Open Steam controller configurator
        </DialogButton>
      </Field>
    </Focusable>
  );
};

export { SteamInputRadialMenu };
