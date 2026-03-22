import { useEffect, useMemo, useRef, useState } from "react";
import { init, type WalineInstance } from "@waline/client";
import "@waline/client/style";
import { BadgeCheck, MessageCircleMore, Sparkles, SmilePlus } from "lucide-react";
import {
  DEFAULT_COMMUNITY_CONFIG,
  buildWalineRuntimeOptions,
  loadCommunityConfig,
  type CommunityConfig,
  type CommunitySurface,
} from "@/lib/community-config";
import "./WalineSurface.css";

export interface WalineSurfaceProps {
  surface: CommunitySurface;
  slug?: string;
  title?: string;
  description?: string;
  className?: string;
  communityConfig?: CommunityConfig | null;
}

const defaultSubtitle = "昵称必填，邮箱可选，支持 Markdown / GFM、表情包搜索和更克制的头像呈现。";

const featurePills = [
  { icon: BadgeCheck, label: "昵称必填" },
  { icon: SmilePlus, label: "表情包" },
  { icon: Sparkles, label: "Enjoy 搜索" },
  { icon: MessageCircleMore, label: "Markdown" },
];

const loadingCopy = "正在载入评论配置...";

const WalineSurface = ({
  surface,
  slug,
  title,
  description,
  className,
  communityConfig,
}: WalineSurfaceProps) => {
  const [remoteConfig, setRemoteConfig] = useState<CommunityConfig | null>(communityConfig ?? null);
  const [loading, setLoading] = useState(!communityConfig);
  const hostRef = useRef<HTMLDivElement | null>(null);
  const instanceRef = useRef<WalineInstance | null>(null);

  useEffect(() => {
    let active = true;

    if (communityConfig) {
      setRemoteConfig(communityConfig);
      setLoading(false);
      return () => {
        active = false;
      };
    }

    setLoading(true);
    void (async () => {
      const config = await loadCommunityConfig();
      if (!active) return;
      setRemoteConfig(config);
      setLoading(false);
    })();

    return () => {
      active = false;
    };
  }, [communityConfig]);

  const resolvedConfig = remoteConfig ?? DEFAULT_COMMUNITY_CONFIG;
  const runtimeOptions = useMemo(
    () => buildWalineRuntimeOptions(resolvedConfig, surface, slug),
    [resolvedConfig, surface, slug],
  );
  const subtitle = description ?? resolvedConfig.helperCopy ?? defaultSubtitle;
  const hasServer = runtimeOptions.serverURL.trim().length > 0;

  useEffect(() => {
    if (loading || !hasServer || !hostRef.current) {
      instanceRef.current?.destroy();
      instanceRef.current = null;
      return;
    }

    instanceRef.current?.destroy();
    instanceRef.current = init({
      ...runtimeOptions,
      el: hostRef.current,
    });

    return () => {
      instanceRef.current?.destroy();
      instanceRef.current = null;
    };
  }, [hasServer, loading, runtimeOptions]);

  return (
    <section className={`aerisun-waline-shell ${className ?? ""}`.trim()}>
      <div className="aerisun-waline-shell__glow" aria-hidden="true" />
      <div className="aerisun-waline-shell__header">
        <div className="space-y-2">
          <p className="aerisun-waline-shell__eyebrow">
            <span className="inline-flex items-center gap-2">
              <MessageCircleMore className="h-4 w-4" />
              社区评论
            </span>
          </p>
          <div className="space-y-1">
            <h2 className="aerisun-waline-shell__title">{title ?? "评论区"}</h2>
            <p className="aerisun-waline-shell__subtitle">{subtitle}</p>
          </div>
        </div>

        <div className="aerisun-waline-shell__pills" aria-label="Waline capabilities">
          {featurePills.map((pill) => {
            const Icon = pill.icon;
            return (
              <span key={pill.label} className="aerisun-waline-shell__pill">
                <Icon className="h-3.5 w-3.5" />
                {pill.label}
              </span>
            );
          })}
        </div>
      </div>

      <div className="aerisun-waline-shell__body">
        {loading ? (
          <div className="aerisun-waline-shell__loading" role="status" aria-live="polite">
            <div className="aerisun-waline-shell__spinner" />
            <p>{loadingCopy}</p>
          </div>
        ) : hasServer ? (
          <div ref={hostRef} className="aerisun-waline-host">
            <div className="sr-only">
              {title ?? "评论区"} {subtitle}
            </div>
          </div>
        ) : (
          <div className="aerisun-waline-shell__empty" role="status">
            <p className="text-sm font-medium text-foreground/80">Waline 服务未配置</p>
            <p className="mt-2 text-sm leading-6 text-foreground/55">
              需要在公开社区配置或 `VITE_WALINE_SERVER_URL` 中提供服务地址后，这个评论区才会显示。
            </p>
          </div>
        )}
      </div>
    </section>
  );
};

export default WalineSurface;
