import { useState, useEffect, useRef, useCallback } from "react"
import { useNavigate } from "react-router-dom"
import { motion, AnimatePresence } from "motion/react"
import { Search, X, FileText, BookOpen, MessageSquare, Quote } from "lucide-react"
import { searchContentApiV1SiteSearchGet } from "@serino/api-client/site"
import { useFrontendI18n } from "@/i18n"

interface SearchResult {
  type: string
  slug: string
  title: string
  snippet: string
  published_at: string | null
}

const TYPE_CONFIG: Record<string, { typeKey: string; icon: typeof FileText; color: string; prefix: string }> = {
  posts: { typeKey: "search.type.posts", icon: FileText, color: "rgb(var(--shiro-accent-rgb)/0.7)", prefix: "/posts" },
  diary: { typeKey: "search.type.diary", icon: BookOpen, color: "rgb(59 130 246 / 0.7)", prefix: "/diary" },
  thoughts: { typeKey: "search.type.thoughts", icon: MessageSquare, color: "rgb(168 85 247 / 0.7)", prefix: "/thoughts" },
  excerpts: { typeKey: "search.type.excerpts", icon: Quote, color: "rgb(234 179 8 / 0.7)", prefix: "/excerpts" },
}

interface SearchModalProps {
  open: boolean
  onClose: () => void
}

const SearchModal = ({ open, onClose }: SearchModalProps) => {
  const { t } = useFrontendI18n()
  const [query, setQuery] = useState("")
  const [results, setResults] = useState<SearchResult[]>([])
  const [loading, setLoading] = useState(false)
  const [searched, setSearched] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const navigate = useNavigate()
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    if (open) {
      setQuery("")
      setResults([])
      setSearched(false)
      setTimeout(() => inputRef.current?.focus(), 100)
    }
  }, [open])

  const doSearch = useCallback(async (q: string) => {
    if (!q.trim()) {
      setResults([])
      setSearched(false)
      return
    }
    setLoading(true)
    try {
      const response = await searchContentApiV1SiteSearchGet({ q: q.trim(), limit: 10 })
      if ("items" in response.data && Array.isArray(response.data.items)) {
        setResults(response.data.items as unknown as SearchResult[])
      } else {
        setResults([])
      }
      setSearched(true)
    } catch {
      setResults([])
      setSearched(true)
    } finally {
      setLoading(false)
    }
  }, [])

  const handleChange = (value: string) => {
    setQuery(value)
    if (timerRef.current) clearTimeout(timerRef.current)
    timerRef.current = setTimeout(() => doSearch(value), 300)
  }

  const handleSelect = (result: SearchResult) => {
    const cfg = TYPE_CONFIG[result.type]
    if (cfg) {
      navigate(`${cfg.prefix}/${result.slug}`)
      onClose()
    }
  }

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && open) {
        e.preventDefault()
        onClose()
      }
    }
    document.addEventListener("keydown", onKey)
    return () => document.removeEventListener("keydown", onKey)
  }, [open, onClose])

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          className="fixed inset-0 z-50 flex items-start justify-center pt-[15vh]"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.15 }}
        >
          <div className="fixed inset-0 bg-background/60 backdrop-blur-sm" onClick={onClose} />
          <motion.div
            className="relative z-10 w-full max-w-lg mx-4 rounded-2xl liquid-glass border border-[rgb(var(--shiro-border-rgb)/0.2)] shadow-xl overflow-hidden"
            initial={{ opacity: 0, y: -20, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -20, scale: 0.96 }}
            transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
          >
            <div className="flex items-center gap-3 px-4 py-3 border-b border-[rgb(var(--shiro-divider-rgb)/0.15)]">
              <Search className="h-4 w-4 text-foreground/30 shrink-0" />
              <input
                ref={inputRef}
                type="text"
                value={query}
                onChange={(e) => handleChange(e.target.value)}
                placeholder={t("search.placeholder")}
                className="flex-1 bg-transparent text-sm font-body text-foreground placeholder:text-foreground/25 outline-none"
              />
              <kbd className="hidden sm:inline-flex items-center gap-0.5 rounded border border-[rgb(var(--shiro-border-rgb)/0.15)] px-1.5 py-0.5 text-[10px] font-body text-foreground/20">
                ESC
              </kbd>
              <button type="button" onClick={onClose} className="sm:hidden text-foreground/30">
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="max-h-[50vh] overflow-y-auto">
              {loading && (
                <div className="flex items-center justify-center py-8">
                  <div className="h-5 w-5 animate-spin rounded-full border-2 border-foreground/10 border-t-foreground/40" />
                </div>
              )}

              {!loading && searched && results.length === 0 && (
                <div className="py-8 text-center">
                  <p className="text-sm font-body text-foreground/30">{t("search.empty")}</p>
                </div>
              )}

              {!loading && results.length > 0 && (
                <div className="py-1">
                  {results.map((item) => {
                    const cfg = TYPE_CONFIG[item.type] ?? TYPE_CONFIG.posts
                    const Icon = cfg.icon
                    return (
                      <button
                        key={`${item.type}-${item.slug}`}
                        type="button"
                        onClick={() => handleSelect(item)}
                        className="w-full text-left px-4 py-2.5 hover:bg-foreground/[0.04] transition-colors flex items-start gap-3"
                      >
                        <Icon className="h-4 w-4 mt-0.5 shrink-0" style={{ color: cfg.color }} />
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-2">
                            <span className="text-sm font-body text-foreground/70 truncate">{item.title}</span>
                            <span
                              className="shrink-0 rounded px-1.5 py-0.5 text-[10px] font-body"
                              style={{ color: cfg.color, background: `${cfg.color.replace(/[\d.]+\)$/, "0.1)")}` }}
                            >
                              {t(cfg.typeKey)}
                            </span>
                          </div>
                          {item.snippet && (
                            <p
                              className="mt-0.5 text-xs font-body text-foreground/30 line-clamp-2"
                              dangerouslySetInnerHTML={{ __html: item.snippet }}
                            />
                          )}
                        </div>
                      </button>
                    )
                  })}
                </div>
              )}

              {!loading && !searched && (
                <div className="py-8 text-center">
                  <p className="text-xs font-body text-foreground/20">{t("search.hint")}</p>
                </div>
              )}
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}

export default SearchModal
