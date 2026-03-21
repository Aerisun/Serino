import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from "react"
import { API_BASE_URL, ApiError } from "@/lib/api"
import { loadRuntimeConfig, type RuntimeConfigSnapshot } from "@/lib/runtime-config"

interface RuntimeConfigContextValue {
  config: RuntimeConfigSnapshot
}

const RuntimeConfigContext = createContext<RuntimeConfigContextValue | null>(null)

function describeRuntimeConfigError(error: Error | null) {
  if (!error) {
    return "站点配置未加载"
  }

  if (error instanceof ApiError) {
    return `接口请求失败（HTTP ${error.status}）`
  }

  if (error.message === "Failed to fetch") {
    return `无法访问接口 ${API_BASE_URL || "/api"}`
  }

  return error.message
}

export function useSiteConfig() {
  const ctx = useContext(RuntimeConfigContext)
  if (!ctx) throw new Error("useSiteConfig must be used within RuntimeConfigProvider")
  return ctx.config.site
}

export function usePageConfig() {
  const ctx = useContext(RuntimeConfigContext)
  if (!ctx) throw new Error("usePageConfig must be used within RuntimeConfigProvider")
  return ctx.config.pages
}

export function RuntimeConfigProvider({ children }: { children: ReactNode }) {
  const [config, setConfig] = useState<RuntimeConfigSnapshot | null>(null)
  const [error, setError] = useState<Error | null>(null)
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const snapshot = await loadRuntimeConfig()
      setConfig(snapshot)
    } catch (err) {
      setError(err instanceof Error ? err : new Error("Failed to load config"))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  if (loading) {
    return (
      <div className="fixed inset-0 flex items-center justify-center bg-background">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-foreground/20 border-t-foreground/60" />
      </div>
    )
  }

  if (error || !config) {
    const message = describeRuntimeConfigError(error)

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
    )
  }

  return (
    <RuntimeConfigContext.Provider value={{ config }}>
      {children}
    </RuntimeConfigContext.Provider>
  )
}
