type IdleCallbackHandle = number;

type IdleDeadline = {
  didTimeout: boolean;
  timeRemaining: () => number;
};

type IdleCallback = (deadline: IdleDeadline) => void;

type IdleWindow = Window & {
  requestIdleCallback?: (callback: IdleCallback, options?: { timeout?: number }) => IdleCallbackHandle;
  cancelIdleCallback?: (handle: IdleCallbackHandle) => void;
};

export const shouldBackgroundPrefetch = () => {
  if (typeof navigator === "undefined") {
    return true;
  }

  const connection = navigator.connection as
    | {
        saveData?: boolean;
        effectiveType?: string;
      }
    | undefined;

  if (connection?.saveData) {
    return false;
  }

  return connection?.effectiveType !== "slow-2g" && connection?.effectiveType !== "2g";
};

export const scheduleIdleTask = (
  task: () => void,
  timeout = 1_500,
) => {
  if (typeof window === "undefined") {
    task();
    return () => {};
  }

  const idleWindow = window as IdleWindow;

  if (typeof idleWindow.requestIdleCallback === "function") {
    const handle = idleWindow.requestIdleCallback(() => task(), { timeout });
    return () => idleWindow.cancelIdleCallback?.(handle);
  }

  const handle = window.setTimeout(task, 32);
  return () => window.clearTimeout(handle);
};
