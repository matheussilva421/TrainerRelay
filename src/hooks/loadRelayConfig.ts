interface RelayConfigLoadOptions<T> {
  load: () => Promise<T>;
  onReady: (value: T) => void;
  onError: () => void;
  setTimer: (callback: () => void, milliseconds: number) => unknown;
  clearTimer: (handle: unknown) => void;
  timeoutMs: number;
}

export const loadRelayConfigWithTimeout = <T>({
  load,
  onReady,
  onError,
  setTimer,
  clearTimer,
  timeoutMs,
}: RelayConfigLoadOptions<T>): (() => void) => {
  let active = true;
  let settled = false;
  const timer = setTimer(() => {
    if (!active || settled) return;
    settled = true;
    onError();
  }, timeoutMs);

  void Promise.resolve()
    .then(load)
    .then(
      (value) => {
        if (!active || settled) return;
        settled = true;
        clearTimer(timer);
        onReady(value);
      },
      () => {
        if (!active || settled) return;
        settled = true;
        clearTimer(timer);
        onError();
      },
    );

  return () => {
    active = false;
    clearTimer(timer);
  };
};
