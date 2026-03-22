import { useState } from "react";
import { Copy, Check, Share2 } from "lucide-react";

interface ShareButtonsProps {
  title: string;
  url?: string;
}

export default function ShareButtons({ title, url }: ShareButtonsProps) {
  const [copied, setCopied] = useState(false);
  const shareUrl = url || (typeof window !== "undefined" ? window.location.href : "");

  const copyLink = async () => {
    try {
      await navigator.clipboard.writeText(shareUrl);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // fallback for older browsers
    }
  };

  const shareToTwitter = () => {
    window.open(
      `https://x.com/intent/tweet?text=${encodeURIComponent(title)}&url=${encodeURIComponent(shareUrl)}`,
      "_blank",
      "noopener,noreferrer"
    );
  };

  const shareToWeibo = () => {
    window.open(
      `https://service.weibo.com/share/share.php?title=${encodeURIComponent(title)}&url=${encodeURIComponent(shareUrl)}`,
      "_blank",
      "noopener,noreferrer"
    );
  };

  const nativeShare = async () => {
    if (navigator.share) {
      try {
        await navigator.share({ title, url: shareUrl });
      } catch {
        // user cancelled
      }
    }
  };

  const buttonClass =
    "inline-flex items-center gap-1.5 rounded-lg border border-[rgb(var(--shiro-border-rgb)/0.16)] bg-foreground/[0.03] px-3 py-1.5 text-xs font-body text-foreground/30 transition-colors hover:border-[rgb(var(--shiro-accent-rgb)/0.28)] hover:text-[rgb(var(--shiro-accent-rgb)/0.78)] hover:bg-[rgb(var(--shiro-accent-rgb)/0.06)]";

  return (
    <div className="mt-6 mb-2 flex flex-wrap items-center justify-center gap-2">
      <button type="button" onClick={copyLink} className={buttonClass}>
        {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
        {copied ? "\u5DF2\u590D\u5236" : "\u590D\u5236\u94FE\u63A5"}
      </button>
      <button type="button" onClick={shareToTwitter} className={buttonClass}>
        <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="currentColor"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" /></svg>
        Twitter
      </button>
      <button type="button" onClick={shareToWeibo} className={buttonClass}>
        <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="currentColor"><path d="M10.098 20.323c-3.977.391-7.414-1.406-7.672-4.02-.259-2.609 2.759-5.047 6.74-5.441 3.979-.394 7.413 1.404 7.671 4.018.259 2.6-2.759 5.049-6.739 5.443zM9.05 17.219c-.384.616-1.208.884-1.829.602-.612-.279-.793-.991-.406-1.593.379-.595 1.176-.86 1.799-.577.631.283.822.987.436 1.568zm1.6-1.999c-.146.232-.465.348-.709.253-.243-.093-.317-.369-.172-.593.142-.224.453-.34.696-.25.245.088.326.362.185.59zm.706-4.716c-2.142-.547-4.553.632-5.479 2.658-.942 2.064-.263 4.338 1.605 5.086 1.94.776 4.452-.395 5.39-2.585.93-2.16.113-4.548-1.516-5.159zM17.727 3.472c-1.809-.675-3.896.099-4.695 1.727-.8 1.622-.128 3.501 1.5 4.216 1.662.737 3.83-.069 4.615-1.758.783-1.681.028-3.508-1.42-4.185zm-.912 3.326c-.316.623-1.025.9-1.584.612-.557-.287-.73-.96-.388-1.577.333-.624 1.068-.908 1.613-.6.551.303.706.967.359 1.565z" /></svg>
        {"\u5FAE\u535A"}
      </button>
      {typeof navigator !== "undefined" && "share" in navigator && (
        <button type="button" onClick={nativeShare} className={buttonClass}>
          <Share2 className="h-3.5 w-3.5" />
          {"\u5206\u4EAB"}
        </button>
      )}
    </div>
  );
}
