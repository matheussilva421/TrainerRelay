export interface BrowserTimerScope {
  setInterval(callback: () => void, milliseconds: number): number;
  clearInterval(handle?: number): void;
  setTimeout(callback: () => void, milliseconds: number): number;
  clearTimeout(handle?: number): void;
}

export const bindBrowserTimers = (scope: BrowserTimerScope) => ({
  setInterval: (callback: () => void, milliseconds: number): unknown => scope.setInterval(callback, milliseconds),
  clearInterval: (handle: unknown): void => scope.clearInterval(handle as number),
  setTimeout: (callback: () => void, milliseconds: number): unknown => scope.setTimeout(callback, milliseconds),
  clearTimeout: (handle: unknown): void => scope.clearTimeout(handle as number),
});
