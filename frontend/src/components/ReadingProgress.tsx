import { useState, useEffect, useCallback } from "react"
import { useLocation } from "react-router-dom"

const DETAIL_PATTERNS = [/^\/posts\//, /^\/diary\//]

const ReadingProgress = () => {
  const { pathname } = useLocation()
  const [progress, setProgress] = useState(0)
  const isDetailPage = DETAIL_PATTERNS.some((p) => p.test(pathname))

  const updateProgress = useCallback(() => {
    const scrollTop = window.scrollY
    const docHeight = document.documentElement.scrollHeight - window.innerHeight
    if (docHeight > 0) {
      setProgress(Math.min(100, (scrollTop / docHeight) * 100))
    }
  }, [])

  useEffect(() => {
    if (!isDetailPage) return
    window.addEventListener("scroll", updateProgress, { passive: true })
    updateProgress()
    return () => window.removeEventListener("scroll", updateProgress)
  }, [isDetailPage, updateProgress])

  if (!isDetailPage || progress <= 0) return null

  return (
    <div className="fixed top-0 left-0 right-0 z-50 h-0.5">
      <div
        className="h-full transition-[width] duration-100 ease-out"
        style={{
          width: `${progress}%`,
          background: "rgb(var(--shiro-accent-rgb))",
        }}
      />
    </div>
  )
}

export default ReadingProgress
