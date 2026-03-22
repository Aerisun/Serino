import { useState, useEffect, useRef } from "react"
import { motion, AnimatePresence } from "motion/react"
import { Link2, X } from "lucide-react"

interface ShareBarProps {
  title: string
  url?: string
}

const WeiboIcon = () => (
  <svg viewBox="0 0 24 24" className="h-4 w-4" fill="currentColor">
    <path d="M10.1 18.3c-3.3.3-6.2-1.2-6.4-3.4-.2-2.2 2.3-4.3 5.6-4.6 3.3-.3 6.2 1.2 6.4 3.4.2 2.2-2.3 4.3-5.6 4.6zm6.7-9.3c-.3-.1-.5-.2-.4-.5.2-.6.2-1.2.1-1.7-.4-1.8-2.4-2.6-4.7-2.2-.2 0-.3 0-.3-.2s0-.3.2-.4c2.7-.6 5.1.5 5.6 2.6.2.8.1 1.5-.2 2.1-.1.2-.2.3-.3.3zM20 8.6c-.6-2.8-3.4-4.3-6.8-3.6-.4.1-.6-.1-.6-.4.1-.4.3-.5.6-.6C17.2 3 20.7 5 21.4 8.2c.3 1.3.1 2.5-.5 3.5-.1.2-.3.3-.5.2-.2-.1-.3-.3-.2-.5.4-.8.5-1.7.3-2.8z"/>
    <path d="M11.5 16.3c-1.6.2-3-.5-3.1-1.5-.1-1 1.1-2 2.7-2.2 1.6-.2 3 .5 3.1 1.5.1 1-1.1 2-2.7 2.2z"/>
  </svg>
)

const TwitterIcon = () => (
  <svg viewBox="0 0 24 24" className="h-4 w-4" fill="currentColor">
    <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/>
  </svg>
)

const WechatIcon = () => (
  <svg viewBox="0 0 24 24" className="h-4 w-4" fill="currentColor">
    <path d="M8.691 2.188C3.891 2.188 0 5.476 0 9.53c0 2.212 1.17 4.203 3.002 5.55a.59.59 0 0 1 .213.665l-.39 1.48c-.019.07-.048.141-.048.213 0 .163.13.295.29.295a.326.326 0 0 0 .167-.054l1.903-1.114a.864.864 0 0 1 .717-.098 10.16 10.16 0 0 0 2.837.403c.276 0 .543-.027.811-.05-.857-2.578.157-4.972 1.932-6.446 1.703-1.415 3.882-1.98 5.853-1.838-.576-3.583-4.196-6.348-8.596-6.348zM5.785 5.991c.642 0 1.162.529 1.162 1.18a1.17 1.17 0 0 1-1.162 1.178A1.17 1.17 0 0 1 4.623 7.17c0-.651.52-1.18 1.162-1.18zm5.813 0c.642 0 1.162.529 1.162 1.18a1.17 1.17 0 0 1-1.162 1.178 1.17 1.17 0 0 1-1.162-1.178c0-.651.52-1.18 1.162-1.18zm5.34 2.867c-1.797-.052-3.746.512-5.28 1.786-1.72 1.428-2.687 3.72-1.78 6.22.942 2.453 3.666 4.229 6.884 4.229.826 0 1.622-.12 2.361-.336a.722.722 0 0 1 .598.082l1.584.926a.272.272 0 0 0 .14.047c.134 0 .24-.11.24-.245 0-.06-.024-.12-.04-.178l-.327-1.233a.49.49 0 0 1 .177-.554C23.212 18.153 24 16.645 24 14.995c0-3.256-3.047-5.944-7.062-6.137zm-2.033 2.86c.535 0 .969.44.969.982a.976.976 0 0 1-.969.983.976.976 0 0 1-.969-.983c0-.542.434-.982.97-.982zm4.842 0c.535 0 .969.44.969.982a.976.976 0 0 1-.969.983.976.976 0 0 1-.969-.983c0-.542.434-.982.97-.982z"/>
  </svg>
)

const ShareBar = ({ title, url: propUrl }: ShareBarProps) => {
  const [copied, setCopied] = useState(false)
  const [qrOpen, setQrOpen] = useState(false)
  const qrRef = useRef<HTMLCanvasElement>(null)
  const shareUrl = propUrl || (typeof window !== "undefined" ? window.location.href : "")

  const copyLink = async () => {
    try {
      await navigator.clipboard.writeText(shareUrl)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch { /* ignore */ }
  }

  const shareWeibo = () => {
    window.open(
      `https://service.weibo.com/share/share.php?url=${encodeURIComponent(shareUrl)}&title=${encodeURIComponent(title)}`,
      "_blank",
      "width=600,height=500"
    )
  }

  const shareTwitter = () => {
    window.open(
      `https://twitter.com/intent/tweet?url=${encodeURIComponent(shareUrl)}&text=${encodeURIComponent(title)}`,
      "_blank",
      "width=600,height=500"
    )
  }

  useEffect(() => {
    if (!qrOpen || !qrRef.current) return
    import("qrcode").then((QRCode) => {
      QRCode.toCanvas(qrRef.current, shareUrl, {
        width: 180,
        margin: 2,
        color: { dark: "#000000", light: "#ffffff" },
      })
    })
  }, [qrOpen, shareUrl])

  const btnClass =
    "inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-body text-foreground/40 liquid-glass border border-[rgb(var(--shiro-border-rgb)/0.15)] transition-colors hover:text-foreground/60 hover:border-[rgb(var(--shiro-accent-rgb)/0.25)]"

  return (
    <div className="mt-6 mb-4">
      <p className="text-[10px] font-body text-foreground/20 uppercase tracking-widest mb-3">分享</p>
      <div className="flex flex-wrap gap-2">
        <button type="button" onClick={() => setQrOpen(true)} className={btnClass}>
          <WechatIcon /> 微信
        </button>
        <button type="button" onClick={shareWeibo} className={btnClass}>
          <WeiboIcon /> 微博
        </button>
        <button type="button" onClick={shareTwitter} className={btnClass}>
          <TwitterIcon /> Twitter
        </button>
        <button type="button" onClick={copyLink} className={btnClass}>
          <Link2 className="h-3.5 w-3.5" /> {copied ? "已复制" : "复制链接"}
        </button>
      </div>

      {/* QR Code Modal */}
      <AnimatePresence>
        {qrOpen && (
          <motion.div
            className="fixed inset-0 z-50 flex items-center justify-center"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          >
            <div className="fixed inset-0 bg-background/60 backdrop-blur-sm" onClick={() => setQrOpen(false)} />
            <motion.div
              className="relative z-10 rounded-2xl liquid-glass border border-[rgb(var(--shiro-border-rgb)/0.2)] p-6 shadow-xl"
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.9, opacity: 0 }}
            >
              <button
                type="button"
                onClick={() => setQrOpen(false)}
                className="absolute top-3 right-3 text-foreground/30 hover:text-foreground/60"
              >
                <X className="h-4 w-4" />
              </button>
              <p className="text-sm font-body text-foreground/60 mb-3 text-center">微信扫码分享</p>
              <canvas ref={qrRef} className="mx-auto rounded-lg" />
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

export default ShareBar
