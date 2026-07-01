import { useEffect } from "react";

export function useResetPendingOnPageRestore(resetPending: () => void) {
  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    const handlePageShow = (event: PageTransitionEvent) => {
      if (event.persisted) {
        resetPending();
      }
    };

    window.addEventListener("pageshow", handlePageShow);
    return () => window.removeEventListener("pageshow", handlePageShow);
  }, [resetPending]);
}
