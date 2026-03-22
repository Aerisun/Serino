import { useEffect, useRef, useState } from "react";
import { init, type WalineInstance } from "@waline/client";
import "@waline/client/style";
import {
  buildWalineRuntimeOptions,
  DEFAULT_COMMUNITY_CONFIG,
  loadCommunityConfig,
  type CommunityConfig,
  type CommunitySurface,
} from "@/lib/community-config";
import "./WalineSurface.css";

export interface WalineSurfaceProps {
  surface: CommunitySurface;
  slug?: string;
  className?: string;
  communityConfig?: CommunityConfig | null;
}

const WalineSurface = ({
  surface,
  slug,
  className,
  communityConfig,
}: WalineSurfaceProps) => {
  const [config, setConfig] = useState<CommunityConfig | null>(
    communityConfig ?? null,
  );
  const [loading, setLoading] = useState(!communityConfig);
  const hostRef = useRef<HTMLDivElement | null>(null);
  const instanceRef = useRef<WalineInstance | null>(null);

  useEffect(() => {
    if (communityConfig) {
      setConfig(communityConfig);
      setLoading(false);
      return;
    }

    let active = true;
    setLoading(true);
    void loadCommunityConfig().then((c) => {
      if (active) {
        setConfig(c);
        setLoading(false);
      }
    });
    return () => {
      active = false;
    };
  }, [communityConfig]);

  useEffect(() => {
    const resolved = config ?? DEFAULT_COMMUNITY_CONFIG;
    if (loading || !resolved.serverURL.trim() || !hostRef.current) {
      return;
    }

    const options = buildWalineRuntimeOptions(resolved, surface, slug);
    instanceRef.current?.destroy();
    instanceRef.current = init({
      ...options,
      emoji: options.emoji as never,
      el: hostRef.current,
    });

    return () => {
      instanceRef.current?.destroy();
      instanceRef.current = null;
    };
  }, [config, loading, surface, slug]);

  const resolved = config ?? DEFAULT_COMMUNITY_CONFIG;
  const hasServer = resolved.serverURL.trim().length > 0;

  if (loading) {
    return (
      <div className="aerisun-waline-loading">正在载入评论...</div>
    );
  }

  if (!hasServer) {
    return (
      <div className="aerisun-waline-empty">
        Waline 服务未配置，需要在社区配置或环境变量中提供服务地址。
      </div>
    );
  }

  return (
    <div
      ref={hostRef}
      className={`aerisun-waline-host ${className ?? ""}`.trim()}
    />
  );
};

export default WalineSurface;
