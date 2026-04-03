import { useEffect, useState } from "react";

type Dependency = string | number | boolean | null | undefined;

export function useDeferredActivation(enabled: boolean, deps: Dependency[] = []) {
  const [active, setActive] = useState(false);
  const depsKey = deps.join("|");

  useEffect(() => {
    if (!enabled) {
      setActive(false);
      return;
    }

    let cancelled = false;
    let timeoutId: number | null = null;
    let idleId: number | null = null;

    const activate = () => {
      if (!cancelled) {
        setActive(true);
      }
    };

    if (typeof window !== "undefined" && "requestIdleCallback" in window) {
      idleId = window.requestIdleCallback(activate, { timeout: 400 });
    } else {
      timeoutId = window.setTimeout(activate, 180);
    }

    return () => {
      cancelled = true;
      if (timeoutId !== null) {
        window.clearTimeout(timeoutId);
      }
      if (idleId !== null && typeof window !== "undefined" && "cancelIdleCallback" in window) {
        window.cancelIdleCallback(idleId);
      }
    };
  }, [enabled, depsKey]);

  return active;
}
