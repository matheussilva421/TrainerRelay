import { callable, type FilePickerRes, FileSelectionType, openFilePicker, type ToastData, toaster } from "@decky/api";
import { logger } from "../utils/logger";

const getEnvironmentValue = callable<[string], string>("get_env");

export const deckyBackend = {
  getEnvironmentValue,
};

export const getHomePath = (): Promise<string> => deckyBackend.getEnvironmentValue("DECKY_USER_HOME");

export type FilePickerFilter = RegExp | ((file: File) => boolean) | undefined;

const rejectionReason = (reason: unknown): string => {
  if (reason instanceof Error) return reason.message;
  if (typeof reason === "string") return reason;
  return "unknown";
};

const selectedExtension = (path: string): string | null => {
  const match = /\.([^.\\/]+)$/.exec(path);
  return match?.[1]?.toLowerCase() ?? null;
};

export const browseFiles = (
  startPath: string,
  includeFiles?: boolean,
  validFileExtensions?: string[],
  filter?: FilePickerFilter,
  defaultHidden?: boolean,
): Promise<FilePickerRes> => {
  logger.info("[TrainerRelay:picker] api-call", {
    hasStartPath: startPath.length > 0,
    includeFiles: Boolean(includeFiles),
    extensions: validFileExtensions ?? [],
  });
  return new Promise((resolve, reject) => {
    openFilePicker(
      FileSelectionType.FILE,
      startPath,
      includeFiles,
      true,
      filter,
      validFileExtensions,
      defaultHidden,
      false,
    ).then(
      (selection) => {
        logger.info("[TrainerRelay:picker] api-resolved", {
          hasPath: selection.path.length > 0,
          extension: selectedExtension(selection.path),
        });
        resolve(selection);
      },
      (reason: unknown) => {
        logger.error("[TrainerRelay:picker] api-rejected", { reason: rejectionReason(reason) });
        reject("User Canceled");
      },
    );
  });
};

export const sendNotice = (msg: string) => {
  const toastData: ToastData = {
    title: "Trainer Relay",
    body: msg,
    duration: 2000,
    playSound: true,
    showToast: true,
  };
  toaster.toast(toastData);
};
