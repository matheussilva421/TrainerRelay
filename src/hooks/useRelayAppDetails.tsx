import type { AppDetails } from "@decky/ui/dist/globals/steam-client/App";
import { useCallback, useEffect, useRef, useState } from "react";
import type { RelayAppDetailsSnapshot, TrainerRelayDetailsState } from "../domain/relay/viewModel";
import { registerForAppDetails, setAppLaunchOptions } from "../infra/steam";

export interface RelayAppDetailsController {
  details: TrainerRelayDetailsState;
  subscribe: (listener: (snapshot: RelayAppDetailsSnapshot) => void) => () => void;
  writeLaunchOptions: (source: string) => void;
}

const isValidAppId = (appid: number): boolean => Number.isSafeInteger(appid) && appid > 0;

const snapshotFromDetails = (details: AppDetails): RelayAppDetailsSnapshot | undefined => {
  if (typeof details.strShortcutExe !== "string" || typeof details.strLaunchOptions !== "string") return undefined;
  return { command: details.strShortcutExe, launchOptions: details.strLaunchOptions };
};

export const useRelayAppDetails = (appid: number): RelayAppDetailsController => {
  const [details, setDetails] = useState<TrainerRelayDetailsState>(
    isValidAppId(appid) ? { status: "loading" } : { status: "error" },
  );
  const listenersRef = useRef(new Set<(snapshot: RelayAppDetailsSnapshot) => void>());

  useEffect(() => {
    listenersRef.current.clear();
    if (!isValidAppId(appid)) {
      setDetails({ status: "error" });
      return;
    }

    let active = true;
    setDetails({ status: "loading" });
    const registration = registerForAppDetails(appid, (rawDetails) => {
      if (!active) return;
      const snapshot = rawDetails ? snapshotFromDetails(rawDetails) : undefined;
      if (!snapshot) {
        setDetails({ status: "error" });
        return;
      }
      setDetails({ status: "ready", snapshot });
      for (const listener of listenersRef.current) listener(snapshot);
    });

    return () => {
      active = false;
      registration.unregister();
      listenersRef.current.clear();
    };
  }, [appid]);

  const subscribe = useCallback((listener: (snapshot: RelayAppDetailsSnapshot) => void) => {
    listenersRef.current.add(listener);
    return () => listenersRef.current.delete(listener);
  }, []);

  const writeLaunchOptions = useCallback(
    (source: string) => {
      if (isValidAppId(appid)) setAppLaunchOptions(appid, source);
    },
    [appid],
  );

  return { details, subscribe, writeLaunchOptions };
};
