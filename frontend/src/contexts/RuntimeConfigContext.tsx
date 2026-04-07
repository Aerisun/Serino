import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { RuntimeConfigContext, describeRuntimeConfigError } from "@/contexts/runtime-config";
import { useFrontendI18n } from "@/i18n";
import { loadRuntimeConfig, type RuntimeConfigSnapshot } from "@/lib/runtime-config";

export function RuntimeConfigProvider({
  children,
  initialConfig = null,
}: {
  children: ReactNode;
  initialConfig?: RuntimeConfigSnapshot | null;
}) {
  const { t } = useFrontendI18n();
  const [config, setConfig] = useState<RuntimeConfigSnapshot | null>(initialConfig);
  const [error, setError] = useState<Error | null>(null);
  const [loading, setLoading] = useState(!initialConfig);
  const configRef = useRef<RuntimeConfigSnapshot | null>(initialConfig);

  useEffect(() => {
    configRef.current = config;
  }, [config]);

  const load = useCallback(async (blocking = false) => {
    if (blocking) {
      setLoading(true);
    }
    try {
      const snapshot = await loadRuntimeConfig();
      setConfig(snapshot);
      setError(null);
    } catch (err) {
      if (!configRef.current) {
        setError(err instanceof Error ? err : new Error("Failed to load config"));
      }
    } finally {
      if (blocking) {
        setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    const hasSeedConfig = Boolean(initialConfig);
    setConfig(initialConfig);
    setLoading(!hasSeedConfig);
    setError(null);
    void load(!hasSeedConfig);
  }, [initialConfig, load]);

  if (loading && !config) {
    return (
      <div className="fixed inset-0 flex items-center justify-center bg-background">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-foreground/20 border-t-foreground/60" />
      </div>
    );
  }

  if ((error || !config) && !config) {
    const message = describeRuntimeConfigError(error);

    return (
      <div className="fixed inset-0 flex flex-col items-center justify-center gap-4 bg-background px-6 text-center">
        <div className="space-y-1">
          <p className="text-sm text-foreground/60">{t("runtime.configLoadFailed")}</p>
          <p className="text-xs text-foreground/40">{message}</p>
        </div>
        <button
          onClick={() => void load(true)}
          className="rounded-full px-5 py-2 text-sm font-medium liquid-glass text-foreground/80 hover:text-foreground transition-colors cursor-pointer"
        >
          {t("common.retry")}
        </button>
      </div>
    );
  }

  return (
    <RuntimeConfigContext.Provider value={{ config }}>{children}</RuntimeConfigContext.Provider>
  );
}
