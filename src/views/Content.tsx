import { DialogButton, Field, Navigation, PanelSection, PanelSectionRow } from "@decky/ui";
import type { FC } from "react";
import { FaGithub } from "react-icons/fa";

const GITHUB = "https://github.com/matheussilva421/TrainerRelay";

const Content: FC = () => {
  const navLink = (url: string) => {
    Navigation.CloseSideMenus();
    Navigation.NavigateToExternalWeb(url);
  };

  return (
    <PanelSection title="Trainer Relay">
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
