import { useEffect, useRef } from "react"
import { getFrontendLang } from "@/i18n"
import { frontendTranslations } from "@/i18n/translations"

// Import Prism core and languages
import Prism from "prismjs"
import "prismjs/components/prism-typescript"
import "prismjs/components/prism-javascript"
import "prismjs/components/prism-css"
import "prismjs/components/prism-python"
import "prismjs/components/prism-bash"
import "prismjs/components/prism-json"
import "prismjs/components/prism-jsx"
import "prismjs/components/prism-tsx"
import "prismjs/components/prism-markup"
import "prismjs/components/prism-yaml"
import "prismjs/components/prism-sql"
import "prismjs/components/prism-go"
import "prismjs/components/prism-rust"

interface CodeHighlighterProps {
  containerRef: React.RefObject<HTMLElement | null>
  content: unknown[] // triggers re-highlight when content changes
}

const CodeHighlighter = ({ containerRef, content }: CodeHighlighterProps) => {
  const processedRef = useRef(new WeakSet<Element>())

  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    const codeBlocks = container.querySelectorAll("pre code")
    codeBlocks.forEach((block) => {
      if (processedRef.current.has(block)) return
      processedRef.current.add(block)

      // Highlight
      Prism.highlightElement(block)

      // Add copy button
      const pre = block.parentElement
      if (pre && !pre.querySelector(".code-copy-btn")) {
        pre.style.position = "relative"
        const btn = document.createElement("button")
        btn.className = "code-copy-btn"
        const lang = getFrontendLang()
        const copyLabel = frontendTranslations[lang]["code.copy"]
        const copiedLabel = frontendTranslations[lang]["code.copied"]
        const failedLabel = frontendTranslations[lang]["code.failed"]
        btn.textContent = copyLabel
        btn.addEventListener("click", async () => {
          try {
            await navigator.clipboard.writeText(block.textContent || "")
            btn.textContent = copiedLabel
            setTimeout(() => { btn.textContent = copyLabel }, 2000)
          } catch {
            btn.textContent = failedLabel
            setTimeout(() => { btn.textContent = copyLabel }, 2000)
          }
        })
        pre.appendChild(btn)
      }
    })
  }, [containerRef, content])

  return null
}

export default CodeHighlighter
