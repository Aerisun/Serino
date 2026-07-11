import { useEffect, useState } from "react";

type Dependency = string | number | boolean | null | undefined;

type DeferredActivationOptions = {
  minimumDelayMs?: number;
};

export function useDeferredActivation(
  enabled: boolean,
  deps: Dependency[] = [],
  options: DeferredActivationOptions = {},
) {
  const [active, setActive] = useState(false);
  const [activeDepsKey, setActiveDepsKey] = useState<string | null>(null);
  const depsKey = deps.join("|");
  const minimumDelayMs = Math.max(0, options.minimumDelayMs ?? 0);

  useEffect(() => {
    if (!enabled) {
      setActive(false);
      setActiveDepsKey(null);
      return;
    }

    let cancelled = false;
    let timeoutId: number | null = null;
    let idleId: number | null = null;
    let delayTimeoutId: number | null = null;

    const activate = () => {
      if (!cancelled) {
        setActiveDepsKey(depsKey);
        setActive(true);
      }
    };

    const queueIdleActivation = () => {
      if (typeof window !== "undefined" && "requestIdleCallback" in window) {
        idleId = window.requestIdleCallback(activate, { timeout: 400 });
      } else {
        timeoutId = window.setTimeout(activate, 180);
      }
    };

    if (minimumDelayMs > 0) {
      delayTimeoutId = window.setTimeout(queueIdleActivation, minimumDelayMs);
    } else {
      queueIdleActivation();
    }

    return () => {
      cancelled = true;
      if (delayTimeoutId !== null) {
        window.clearTimeout(delayTimeoutId);
      }
      if (timeoutId !== null) {
        window.clearTimeout(timeoutId);
      }
      if (idleId !== null && typeof window !== "undefined" && "cancelIdleCallback" in window) {
        window.cancelIdleCallback(idleId);
      }
    };
  }, [enabled, depsKey, minimumDelayMs]);

  return active && activeDepsKey === depsKey;
}
