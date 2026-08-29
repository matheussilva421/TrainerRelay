import { routerHook } from "@decky/api";
import { definePlugin, staticClasses } from "@decky/ui";
import { FaWrench as PluginIcon } from "react-icons/fa";

import contextMenuPatch, { LibraryContextMenu } from "./patch";
import { logger } from "./utils/logger";
import Content from "./views/Content";
import PageRouter from "./views/PageRouter";

export default definePlugin(() => {
  logger.info("[TrainerRelay:picker] plugin-loaded", { diagnosticsVersion: 1 });
  const menuPatches = contextMenuPatch(LibraryContextMenu);

  routerHook.addRoute("/trainer-relay/:appid", PageRouter, { exact: true });

  return {
    title: <div className={staticClasses.Title}>Trainer Relay</div>,
    content: <Content />,
    icon: <PluginIcon />,
    onDismount() {
      routerHook.removeRoute("/trainer-relay/:appid");
      menuPatches?.unpatch();
    },
  };
});
