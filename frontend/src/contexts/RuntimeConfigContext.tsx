import { useCallback, useEffect, useState, type ReactNode } from "react";
import { RuntimeConfigContext, describeRuntimeConfigError } from "@/contexts/runtime-config";
import { loadRuntimeConfig, type RuntimeConfigSnapshot } from "@/lib/runtime-config";

export function RuntimeConfigProvider({ children }: { children: ReactNode }) {
  const [config, setConfig] = useState<RuntimeConfigSnapshot | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const snapshot = await loadRuntimeConfig();
      setConfig(snapshot);
    } catch (err) {
      setError(err instanceof Error ? err : new Error("Failed to load config"));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (loading) {
    return (
      <div className="fixed inset-0 flex items-center justify-center bg-background">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-foreground/20 border-t-foreground/60" />
      </div>
    );
  }

  if (error || !config) {
    const message = describeRuntimeConfigError(error);

    return (
      <div className="fixed inset-0 flex flex-col items-center justify-center gap-4 bg-background px-6 text-center">
        <div className="space-y-1">
          <p className="text-sm text-foreground/60">无法加载站点配置</p>
          <p className="text-xs text-foreground/40">{message}</p>
        </div>
        <button
          onClick={load}
          className="rounded-full px-5 py-2 text-sm font-medium liquid-glass text-foreground/80 hover:text-foreground transition-colors cursor-pointer"
        >
          重试
        </button>
      </div>
    );
  }

  return (
    <RuntimeConfigContext.Provider value={{ config }}>{children}</RuntimeConfigContext.Provider>
  );
}
