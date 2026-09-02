import { DialogButton, Field, Navigation, PanelSection, PanelSectionRow } from "@decky/ui";
import type { FC } from "react";
import { FaGithub } from "react-icons/fa";
import { CheatControlList } from "../components/CheatControlList";
import { ManualCheatEditor } from "../components/ManualCheatEditor";
import { useActiveLaunchIdentity } from "../hooks/useActiveLaunchIdentity";
import { useCheatControls } from "../hooks/useCheatControls";

const GITHUB = "https://github.com/matheussilva421/TrainerRelay";

const Content: FC = () => {
  const identity = useActiveLaunchIdentity();
  const cheatControls = useCheatControls(identity);
  const navLink = (url: string) => {
    Navigation.CloseSideMenus();
    Navigation.NavigateToExternalWeb(url);
  };

  return (
    <PanelSection title="Trainer Relay">
      <PanelSectionRow>
        {cheatControls.response?.status === "ready" ? (
          <>
            <CheatControlList
              controls={cheatControls.response}
              busy={cheatControls.busy}
              onCommand={(cheatId) => cheatControls.sendCommand(cheatId)}
              lastResults={cheatControls.lastResults}
            />
            {cheatControls.response.source === "manual" && (
              <ManualCheatEditor
                ready={true}
                trainerSha256={cheatControls.response.trainerSha256}
                busy={cheatControls.busy}
                cheats={cheatControls.response.cheats}
                onAdd={(label, hotkey) => cheatControls.addManualCheatControl(label, hotkey)}
                onRemove={(cheatId) => cheatControls.removeManualCheatControl(cheatId)}
              />
            )}
          </>
        ) : (
          <Field
            label="Cheat controls"
            description={
              identity
                ? cheatControls.error
                  ? `Controles indisponíveis (${cheatControls.error}). Abra a página do jogo para tentar novamente.`
                  : "Abra a página do jogo para carregar os controles com segurança."
                : "Abra a página do jogo para carregar os controles com segurança."
            }
            padding="standard"
            bottomSeparator="standard"
          />
        )}
      </PanelSectionRow>
      <PanelSectionRow>
        <Field
          label="Epic/GOG trainer sidecars"
          description="Open a supported UniFiDeck game's context menu to configure one trainer for its Wine prefix."
          padding="standard"
          bottomSeparator="standard"
        />
      </PanelSectionRow>
      <PanelSectionRow>
        <Field
          description="This experimental build is fail-closed: unsupported shortcuts and uncertain process matches expose no controls."
          padding="standard"
          bottomSeparator="standard"
        />
      </PanelSectionRow>
      <PanelSectionRow>
        <Field
          description="Source, diagnostics and validation notes"
          padding="standard"
          bottomSeparator="none"
          childrenLayout="below"
        >
          <DialogButton onClick={() => navLink(GITHUB)}>
            <FaGithub /> GitHub
          </DialogButton>
        </Field>
      </PanelSectionRow>
    </PanelSection>
  );
};

export default Content;
