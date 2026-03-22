import { useState, useEffect, useCallback, useRef } from "react"
import { motion, AnimatePresence } from "motion/react"
import { List } from "lucide-react"

interface Heading {
  id: string
  text: string
  level: number
}

interface TableOfContentsProps {
  containerRef: React.RefObject<HTMLElement | null>
  content: unknown[] // triggers re-parse on change
}

const TableOfContents = ({ containerRef, content }: TableOfContentsProps) => {
  const [headings, setHeadings] = useState<Heading[]>([])
  const [activeId, setActiveId] = useState("")
  const [mobileOpen, setMobileOpen] = useState(false)
  const observerRef = useRef<IntersectionObserver | null>(null)

  // Parse headings
  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    const timer = setTimeout(() => {
      const els = container.querySelectorAll("h2, h3")
      const items: Heading[] = []
      els.forEach((el, i) => {
        if (!el.id) el.id = `heading-${i}`
        items.push({
          id: el.id,
          text: el.textContent || "",
          level: el.tagName === "H2" ? 2 : 3,
        })
      })
      setHeadings(items)
    }, 200)

    return () => clearTimeout(timer)
  }, [containerRef, content])

  // Track active heading
  useEffect(() => {
    if (headings.length === 0) return

    observerRef.current?.disconnect()
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            setActiveId(entry.target.id)
            break
          }
        }
      },
      { rootMargin: "-80px 0px -70% 0px", threshold: 0 }
    )
    observerRef.current = observer

    headings.forEach(({ id }) => {
      const el = document.getElementById(id)
      if (el) observer.observe(el)
    })

    return () => observer.disconnect()
  }, [headings])

  const scrollTo = useCallback((id: string) => {
    const el = document.getElementById(id)
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "start" })
      setMobileOpen(false)
    }
  }, [])

  if (headings.length < 2) return null

  const tocContent = (
    <nav className="space-y-0.5">
      {headings.map((h) => (
        <button
          key={h.id}
          type="button"
          onClick={() => scrollTo(h.id)}
          className={`block w-full text-left text-xs font-body transition-colors py-1 ${
            h.level === 3 ? "pl-4" : "pl-0"
          } ${
            activeId === h.id
              ? "text-[rgb(var(--shiro-accent-rgb)/0.85)] border-l-2 border-[rgb(var(--shiro-accent-rgb)/0.6)] pl-2"
              : "text-foreground/30 hover:text-foreground/50"
          }`}
          style={h.level === 3 && activeId === h.id ? { paddingLeft: "1.25rem" } : undefined}
        >
          {h.text}
        </button>
      ))}
    </nav>
  )

  return (
    <>
      {/* Desktop: sticky sidebar */}
      <div className="hidden lg:block fixed right-8 top-32 w-52 max-h-[60vh] overflow-y-auto">
        <p className="text-[10px] font-body text-foreground/20 uppercase tracking-widest mb-2">目录</p>
        {tocContent}
      </div>

      {/* Mobile: collapsible */}
      <div className="lg:hidden mb-6">
        <button
          type="button"
          onClick={() => setMobileOpen(!mobileOpen)}
          className="flex items-center gap-1.5 text-xs font-body text-foreground/30 hover:text-foreground/50 transition-colors"
        >
          <List className="h-3.5 w-3.5" />
          目录 ({headings.length})
        </button>
        <AnimatePresence>
          {mobileOpen && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="overflow-hidden mt-2 pl-2 border-l border-[rgb(var(--shiro-divider-rgb)/0.15)]"
            >
              {tocContent}
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </>
  )
}

export default TableOfContents
