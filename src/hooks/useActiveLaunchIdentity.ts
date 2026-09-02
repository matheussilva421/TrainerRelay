import { Router } from "@decky/ui";
import { useEffect, useState } from "react";
import { classifyShortcut } from "../domain/relay/shortcut";
import type { LaunchIdentity } from "../domain/relay/types";
import { bindBrowserTimers } from "./browserTimers";
import { useRelayAppDetails } from "./useRelayAppDetails";

const invalidAppId = Number.NaN;

export const readMainRunningAppId = (): number => {
  try {
    const appid = Number.parseInt(Router.MainRunningApp?.appid ?? "", 10);
    return Number.isSafeInteger(appid) && appid > 0 ? appid : invalidAppId;
  } catch {
    return invalidAppId;
  }
};

export const useActiveLaunchIdentity = (): LaunchIdentity | undefined => {
  const [appid, setAppid] = useState(readMainRunningAppId);
  const appDetails = useRelayAppDetails(appid);

  useEffect(() => {
    const timers = bindBrowserTimers(window);
    const interval = timers.setInterval(() => {
      const next = readMainRunningAppId();
      setAppid((current) => (Object.is(current, next) ? current : next));
    }, 1_000);
    return () => timers.clearInterval(interval);
  }, []);

  if (appDetails.details.status !== "ready") return undefined;
  return classifyShortcut(appDetails.details.snapshot.command, appDetails.details.snapshot.launchOptions);
};
