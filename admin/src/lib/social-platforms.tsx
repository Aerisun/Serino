import { Globe, Link2, Mail, Phone } from "lucide-react";

export interface SocialPlatformPreset {
  key: string;
  label: string;
  iconKey: string;
  urlPlaceholder: string;
}

export const CUSTOM_SOCIAL_PLATFORM_KEY = "custom";

export const SOCIAL_PLATFORM_PRESETS: SocialPlatformPreset[] = [
  { key: "github", label: "GitHub", iconKey: "github", urlPlaceholder: "https://github.com/your-name" },
  { key: "gitlab", label: "GitLab", iconKey: "gitlab", urlPlaceholder: "https://gitlab.com/your-name" },
  { key: "gitee", label: "Gitee", iconKey: "gitee", urlPlaceholder: "https://gitee.com/your-name" },
  { key: "wechat", label: "微信", iconKey: "wechat", urlPlaceholder: "https://u.wechat.com/your-share-link" },
  { key: "qq", label: "QQ", iconKey: "qq", urlPlaceholder: "https://qm.qq.com/q/your-share-link" },
  { key: "feishu", label: "飞书", iconKey: "feishu", urlPlaceholder: "https://www.feishu.cn/your-space" },
  { key: "telegram", label: "Telegram", iconKey: "telegram", urlPlaceholder: "https://t.me/your-name" },
  { key: "discord", label: "Discord", iconKey: "discord", urlPlaceholder: "https://discord.gg/your-invite" },
  { key: "whatsapp", label: "WhatsApp", iconKey: "whatsapp", urlPlaceholder: "https://wa.me/8613800000000" },
  { key: "line", label: "LINE", iconKey: "line", urlPlaceholder: "https://line.me/ti/p/your-id" },
  { key: "facebook", label: "Facebook", iconKey: "facebook", urlPlaceholder: "https://facebook.com/your-name" },
  { key: "instagram", label: "Instagram", iconKey: "instagram", urlPlaceholder: "https://instagram.com/your-name" },
  { key: "linkedin", label: "LinkedIn", iconKey: "linkedin", urlPlaceholder: "https://linkedin.com/in/your-name" },
  { key: "x", label: "X", iconKey: "x", urlPlaceholder: "https://x.com/your-name" },
  { key: "youtube", label: "YouTube", iconKey: "youtube", urlPlaceholder: "https://youtube.com/@your-name" },
  { key: "bilibili", label: "哔哩哔哩", iconKey: "bilibili", urlPlaceholder: "https://space.bilibili.com/your-id" },
  { key: "zhihu", label: "知乎", iconKey: "zhihu", urlPlaceholder: "https://www.zhihu.com/people/your-name" },
  { key: "juejin", label: "稀土掘金", iconKey: "juejin", urlPlaceholder: "https://juejin.cn/user/your-id" },
  { key: "xiaohongshu", label: "小红书", iconKey: "xiaohongshu", urlPlaceholder: "https://www.xiaohongshu.com/user/profile/your-id" },
  { key: "weibo", label: "微博", iconKey: "weibo", urlPlaceholder: "https://weibo.com/your-name" },
  { key: "email", label: "邮箱", iconKey: "email", urlPlaceholder: "mailto:hello@example.com" },
  { key: "phone", label: "电话", iconKey: "phone", urlPlaceholder: "tel:+8613800000000" },
  { key: "website", label: "个人网站", iconKey: "website", urlPlaceholder: "https://your-site.com" },
  { key: "music", label: "网易云音乐", iconKey: "music", urlPlaceholder: "https://music.163.com/#/user/home?id=your-id" },
];

const ICON_KEY_ALIASES: Record<string, string> = {
  netease: "music",
  "netease-music": "music",
  weixin: "wechat",
  lark: "feishu",
  fb: "facebook",
  ig: "instagram",
  mail: "email",
  web: "website",
  site: "website",
  url: "website",
  rednote: "xiaohongshu",
};

const normalizeIconKey = (iconKey: string) => ICON_KEY_ALIASES[iconKey.toLowerCase()] ?? iconKey.toLowerCase();

export const resolveSocialPlatform = (iconKey: string) =>
  SOCIAL_PLATFORM_PRESETS.find((preset) => preset.iconKey === normalizeIconKey(iconKey));

function MonogramIcon({
  label,
  className,
  fontSize = 8.2,
}: {
  label: string;
  className: string;
  fontSize?: number;
}) {
  return (
    <svg viewBox="0 0 24 24" fill="none" className={className}>
      <circle cx="12" cy="12" r="9" fill="currentColor" opacity="0.12" />
      <text
        x="12"
        y="13.2"
        fill="currentColor"
        fontFamily="ui-sans-serif, system-ui, sans-serif"
        fontSize={fontSize}
        fontWeight="700"
        letterSpacing="0.02em"
        textAnchor="middle"
      >
        {label}
      </text>
    </svg>
  );
}

export function SocialPlatformIcon({ iconKey, className = "h-4 w-4" }: { iconKey: string; className?: string }) {
  switch (normalizeIconKey(iconKey)) {
    case "github":
      return (
        <svg viewBox="0 0 24 24" fill="currentColor" className={className}>
          <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z" />
        </svg>
      );
    case "telegram":
      return (
        <svg viewBox="0 0 24 24" fill="currentColor" className={className}>
          <path d="M11.944 0A12 12 0 000 12a12 12 0 0012 12 12 12 0 0012-12A12 12 0 0012 0a12 12 0 00-.056 0zm4.962 7.224c.1-.002.321.023.465.14a.506.506 0 01.171.325c.016.093.036.306.02.472-.18 1.898-.962 6.502-1.36 8.627-.168.9-.499 1.201-.82 1.23-.696.065-1.225-.46-1.9-.902-1.056-.693-1.653-1.124-2.678-1.8-1.185-.78-.417-1.21.258-1.91.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.14-5.061 3.345-.48.33-.913.49-1.302.48-.428-.008-1.252-.241-1.865-.44-.752-.245-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.83-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476-1.635z" />
        </svg>
      );
    case "x":
      return (
        <svg viewBox="0 0 24 24" fill="currentColor" className={className}>
          <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" />
        </svg>
      );
    case "music":
      return (
        <svg viewBox="0 0 24 24" fill="currentColor" className={className}>
          <path d="M12 0C5.372 0 0 5.372 0 12s5.372 12 12 12 12-5.372 12-12S18.628 0 12 0zm5.92 17.108c-.745 1.222-1.86 2.068-3.327 2.528-1.378.43-2.71.404-3.996-.08a5.07 5.07 0 01-2.715-2.244c-.674-1.166-.796-2.418-.364-3.746.336-1.032.893-1.907 1.671-2.62.81-.742 1.756-1.207 2.834-1.393.332-.058.666-.076 1-.054.51.034.924.267 1.242.684.318.418.45.895.394 1.43a2.38 2.38 0 01-.564 1.282c-.37.436-.856.7-1.46.792-.39.06-.773.032-1.15-.084a1.474 1.474 0 01-.923-.782c-.11-.228-.15-.472-.122-.73.04-.356.186-.654.44-.894.046-.044.094-.086.144-.126l.11-.086c.07-.05.078-.09.024-.12-.12-.066-.252-.078-.396-.034-.36.11-.648.336-.864.678-.328.52-.408 1.08-.24 1.682.2.718.626 1.24 1.278 1.566.754.378 1.548.434 2.382.17a3.823 3.823 0 002.172-1.75c.43-.796.572-1.648.424-2.554-.19-1.174-.74-2.138-1.648-2.89a5.1 5.1 0 00-2.83-1.188c-1.136-.134-2.216.05-3.242.55-1.322.646-2.27 1.636-2.842 2.97-.442 1.028-.58 2.1-.416 3.216.21 1.42.848 2.614 1.912 3.582 1.128 1.028 2.47 1.598 4.024 1.712.37.028.74.018 1.11-.028.168-.02.266.044.294.192.018.1-.02.178-.114.234-.118.07-.248.112-.388.124-.64.058-1.274.04-1.9-.054z" />
        </svg>
      );
    case "wechat":
      return (
        <svg viewBox="0 0 24 24" fill="currentColor" className={className}>
          <path d="M8.86 4.24c-3.6 0-6.48 2.27-6.48 5.08 0 1.53.9 2.92 2.38 3.88L4 16.94l3.49-1.73c.46.07.92.1 1.37.1 3.58 0 6.47-2.27 6.47-5.08 0-2.81-2.89-4.99-6.47-4.99Zm-2.23 4.2a.86.86 0 1 1 0 1.72.86.86 0 0 1 0-1.71Zm4.45 0a.86.86 0 1 1 0 1.72.86.86 0 0 1 0-1.71Z" />
          <path d="M16.56 8.65c-2.92 0-5.28 1.84-5.28 4.11 0 1.19.65 2.28 1.73 3.03l-.55 2.69 2.65-1.32c.47.08.95.13 1.45.13 2.9 0 5.26-1.84 5.26-4.12 0-2.27-2.36-4.09-5.26-4.09Zm-1.85 2.6a.7.7 0 1 1 0 1.4.7.7 0 0 1 0-1.4Zm3.7 0a.7.7 0 1 1 0 1.4.7.7 0 0 1 0-1.4Z" />
        </svg>
      );
    case "qq":
      return <MonogramIcon label="QQ" className={className} fontSize={7.2} />;
    case "feishu":
      return (
        <svg viewBox="0 0 24 24" fill="currentColor" className={className}>
          <path d="M5.34 8.4 14.98 4.8c1.13-.42 2.1.72 1.63 1.8l-1.28 2.96 4.46.3c1.27.08 1.76 1.73.76 2.5L8.92 20.7c-1.07.77-2.47-.25-2.03-1.5l1.55-4.36-3-.22c-1.2-.08-1.7-1.55-.8-2.22Z" />
        </svg>
      );
    case "discord":
      return (
        <svg viewBox="0 0 24 24" fill="currentColor" className={className}>
          <path d="M7.23 7.3c3.34-1.13 6.2-1.13 9.54 0 1.43 1.62 2.28 3.69 2.46 6.09 0 0-1.38 1.06-4.18 1.57-.34-.45-.67-.93-.95-1.43.48-.12.94-.3 1.38-.52-.27-.18-.55-.33-.84-.48-1.7.8-3.57.8-5.26 0-.29.15-.57.3-.84.48.44.22.9.4 1.38.52-.28.5-.6.98-.96 1.43-2.78-.5-4.17-1.57-4.17-1.57.18-2.4 1.02-4.47 2.44-6.09Zm3.21 4.06a1.17 1.17 0 1 0 0 2.33 1.17 1.17 0 0 0 0-2.33Zm3.12 0a1.17 1.17 0 1 0 0 2.33 1.17 1.17 0 0 0 0-2.33Z" />
        </svg>
      );
    case "whatsapp":
      return (
        <svg viewBox="0 0 24 24" fill="currentColor" className={className}>
          <path d="M12.02 2.2A9.8 9.8 0 0 0 4.3 17.98L3 22l4.14-1.2a9.82 9.82 0 1 0 4.88-18.6Zm0 17.64a7.8 7.8 0 0 1-3.98-1.08l-.3-.18-2.46.72.8-2.39-.2-.32a7.8 7.8 0 1 1 6.14 3.25Zm4.26-5.8c-.23.65-1.16 1.2-1.9 1.34-.5.08-1.16.15-3.36-.76-2.8-1.17-4.61-4-4.75-4.19-.14-.19-1.14-1.51-1.14-2.88 0-1.37.73-2.03.98-2.32.24-.27.52-.33.7-.33h.5c.16 0 .4-.06.62.46.24.56.82 1.92.89 2.06.07.15.12.33.02.53-.1.19-.16.31-.33.49-.16.18-.34.4-.49.54-.16.16-.32.34-.14.66.18.31.8 1.32 1.72 2.13 1.18 1.04 2.17 1.36 2.47 1.52.3.16.47.14.65-.1.18-.23.76-.88.96-1.18.2-.3.42-.25.7-.15.28.1 1.8.85 2.1 1 .3.16.49.23.56.36.08.12.08.72-.15 1.37Z" />
        </svg>
      );
    case "line":
      return (
        <svg viewBox="0 0 24 24" fill="currentColor" className={className}>
          <path d="M12 3.4c-4.9 0-8.9 3.24-8.9 7.22 0 3.56 3.17 6.54 7.45 7.08l.26 2.9 2.68-2.63c4.42-.35 7.9-3.37 7.9-7.35 0-3.98-4-7.22-8.9-7.22Zm-3 8.32H7.64V9h1.37Zm2.96 0H9.97V9h1.37v1.4h.62Zm0 3.02H9V9h1.37v3.33h1.6Zm4.44-1.92h-1.84v.63h1.84v1.3h-3.2V9h3.2v1.3h-1.84v.57h1.84Z" />
        </svg>
      );
    case "facebook":
      return (
        <svg viewBox="0 0 24 24" fill="currentColor" className={className}>
          <path d="M13.46 21.5v-7.78h2.61l.39-3.03h-3V8.75c0-.88.25-1.48 1.5-1.48h1.6V4.55c-.28-.04-1.24-.12-2.35-.12-2.32 0-3.91 1.42-3.91 4.02v2.24H7.66v3.03h2.64v7.78h3.16Z" />
        </svg>
      );
    case "instagram":
      return (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className={className}>
          <rect x="4" y="4" width="16" height="16" rx="4.5" />
          <circle cx="12" cy="12" r="3.6" />
          <circle cx="17.2" cy="6.8" r="1" fill="currentColor" stroke="none" />
        </svg>
      );
    case "linkedin":
      return (
        <svg viewBox="0 0 24 24" fill="currentColor" className={className}>
          <path d="M6.15 8.26a1.43 1.43 0 1 1 0-2.86 1.43 1.43 0 0 1 0 2.86ZM4.93 18.7h2.45V9.8H4.93v8.9Zm4 0h2.45v-4.53c0-1.2.23-2.35 1.72-2.35 1.47 0 1.49 1.38 1.49 2.43v4.45H17V13.7c0-2.46-.53-4.36-3.4-4.36-1.39 0-2.32.76-2.7 1.49h-.04V9.8H8.93c.03.68 0 8.9 0 8.9Z" />
        </svg>
      );
    case "youtube":
      return (
        <svg viewBox="0 0 24 24" fill="currentColor" className={className}>
          <path d="M21.58 7.2a2.7 2.7 0 0 0-1.9-1.91C18 4.8 12 4.8 12 4.8s-6 0-7.69.49A2.7 2.7 0 0 0 2.4 7.2c-.5 1.7-.5 4.8-.5 4.8s0 3.1.5 4.8a2.7 2.7 0 0 0 1.91 1.91c1.69.49 7.69.49 7.69.49s6 0 7.69-.49a2.7 2.7 0 0 0 1.9-1.91c.5-1.7.5-4.8.5-4.8s0-3.1-.5-4.8ZM9.73 15.02V8.98L15.27 12l-5.54 3.02Z" />
        </svg>
      );
    case "bilibili":
      return (
        <svg viewBox="0 0 24 24" fill="currentColor" className={className}>
          <path d="M7.55 4.5 5.9 2.84a.9.9 0 1 0-1.27 1.27L6.86 6.3H5.65A2.65 2.65 0 0 0 3 8.95v8.4A2.65 2.65 0 0 0 5.65 20h12.7A2.65 2.65 0 0 0 21 17.35v-8.4a2.65 2.65 0 0 0-2.65-2.65h-1.2l2.23-2.19a.9.9 0 0 0-1.26-1.28L16.45 4.5h-8.9Zm-.1 3.55h9.1c1.1 0 1.95.85 1.95 1.95v6.3c0 1.1-.85 1.95-1.95 1.95h-9.1c-1.1 0-1.95-.85-1.95-1.95V10c0-1.1.85-1.95 1.95-1.95Zm2.55 3.05a1.15 1.15 0 1 0 0 2.3 1.15 1.15 0 0 0 0-2.3Zm4 0a1.15 1.15 0 1 0 0 2.3 1.15 1.15 0 0 0 0-2.3Z" />
        </svg>
      );
    case "zhihu":
      return <MonogramIcon label="知" className={className} fontSize={9.2} />;
    case "juejin":
      return (
        <svg viewBox="0 0 24 24" fill="currentColor" className={className}>
          <path d="m12 2.7-6.78 4.8 1.65 1.22L12 5.02l5.13 3.7 1.65-1.22L12 2.7Zm0 5.7-4.1 2.92L12 14.2l4.1-2.9L12 8.4Zm-5.95 4.06L11 16.1v3.47L4.6 15.1l1.45-2.64Zm11.9 0 1.45 2.64L13 19.57V16.1l4.95-3.64Z" />
        </svg>
      );
    case "xiaohongshu":
      return <MonogramIcon label="红" className={className} fontSize={9.2} />;
    case "weibo":
      return (
        <svg viewBox="0 0 24 24" fill="currentColor" className={className}>
          <path d="M9.47 10.98c-2.48 0-4.5 1.65-4.5 3.68 0 2.04 2.02 3.69 4.5 3.69 2.49 0 4.5-1.65 4.5-3.69 0-2.03-2.01-3.68-4.5-3.68Zm-.23 5.26c-.76.18-1.45-.16-1.55-.74-.1-.59.43-1.22 1.19-1.4.76-.18 1.45.15 1.56.74.1.58-.43 1.2-1.2 1.4Z" />
          <path d="M15.66 6.15c1.9.2 3.41 1.7 3.61 3.61.03.36.33.64.7.64.4 0 .73-.34.69-.75-.24-2.61-2.3-4.68-4.92-4.92-.4-.04-.75.28-.75.69 0 .37.28.67.67.73Z" />
          <path d="M12.6 8.97c.37-.8.37-1.5-.1-2.06-.62-.73-1.73-.8-2.91-.25-1.03.49-1.6 1.49-1.3 2.33.12.34.1.6-.04.95-.31.73-.2 1.4.3 1.94.77.82 2.2.95 3.62.37 2.02-.82 3.19-2.74 2.7-4.28-.38-1.21-1.47-1.64-2.27-1Z" />
        </svg>
      );
    case "gitlab":
      return <MonogramIcon label="GL" className={className} fontSize={7.1} />;
    case "gitee":
      return <MonogramIcon label="G" className={className} fontSize={8.8} />;
    case "email":
      return <Mail className={className} strokeWidth={1.8} />;
    case "phone":
      return <Phone className={className} strokeWidth={1.8} />;
    case "website":
      return <Globe className={className} strokeWidth={1.8} />;
    default:
      return <Link2 className={className} strokeWidth={1.8} />;
  }
}
