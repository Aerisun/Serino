import { useState, useEffect } from "react"
import { motion, AnimatePresence } from "motion/react"
import { ArrowUp } from "lucide-react"

const BackToTop = () => {
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    const onScroll = () => setVisible(window.scrollY > 300)
    window.addEventListener("scroll", onScroll, { passive: true })
    return () => window.removeEventListener("scroll", onScroll)
  }, [])

  return (
    <AnimatePresence>
      {visible && (
        <motion.button
          type="button"
          initial={{ opacity: 0, scale: 0.8 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: 0.8 }}
          transition={{ duration: 0.2 }}
          onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}
          className="fixed bottom-6 right-6 z-40 flex h-10 w-10 items-center justify-center rounded-full liquid-glass border border-[rgb(var(--shiro-border-rgb)/0.2)] text-foreground/40 shadow-sm transition-colors hover:text-[rgb(var(--shiro-accent-rgb)/0.8)] hover:border-[rgb(var(--shiro-accent-rgb)/0.3)]"
          aria-label="回到顶部"
        >
          <ArrowUp className="h-4 w-4" />
        </motion.button>
      )}
    </AnimatePresence>
  )
}

export default BackToTop
