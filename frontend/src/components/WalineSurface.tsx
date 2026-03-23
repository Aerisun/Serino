import { useCallback, useEffect, useRef, useState } from "react";
import { init, type WalineInstance } from "@waline/client";
import "@waline/client/style";
import {
  buildWalineRuntimeOptions,
  DEFAULT_COMMUNITY_CONFIG,
  loadCommunityConfig,
  type AvatarPreset,
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

/* Waline uses Vue internally — suppress Vue production warnings */
if (typeof globalThis !== "undefined") {
  const g = globalThis as Record<string, unknown>;
  g.__VUE_OPTIONS_API__ = true;
  g.__VUE_PROD_DEVTOOLS__ = false;
  g.__VUE_PROD_HYDRATION_MISMATCH_DETAILS__ = false;
}

const AVATAR_STORAGE_KEY = "aerisun:comment-avatar";

/** Small floating avatar picker triggered by clicking the Waline editor avatar */
const AvatarPicker = ({
  presets,
  onSelect,
  onClose,
}: {
  presets: AvatarPreset[];
  onSelect: (preset: AvatarPreset) => void;
  onClose: () => void;
}) => {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose();
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [onClose]);

  return (
    <div ref={ref} className="aerisun-avatar-picker">
      <div className="aerisun-avatar-picker__title">选择头像</div>
      <div className="aerisun-avatar-picker__grid">
        {presets.map((p) => (
          <button
            key={p.key}
            type="button"
            className="aerisun-avatar-picker__item"
            title={p.label}
            onClick={() => { onSelect(p); onClose(); }}
          >
            <img src={p.avatar_url} alt={p.label} />
          </button>
        ))}
      </div>
    </div>
  );
};

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
  const [pickerOpen, setPickerOpen] = useState(false);
  const [selectedAvatar, setSelectedAvatar] = useState<AvatarPreset | null>(() => {
    try {
      const stored = localStorage.getItem(AVATAR_STORAGE_KEY);
      return stored ? JSON.parse(stored) : null;
    } catch { return null; }
  });
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
      instanceRef.current?.destroy();
      instanceRef.current = null;
      return;
    }

    const options = buildWalineRuntimeOptions(resolved, surface, slug);
    const runtimeOptions = {
      ...options,
      emoji: options.emoji as never,
    };

    if (instanceRef.current) {
      instanceRef.current.update(runtimeOptions);
      return;
    }

    instanceRef.current = init({
      ...runtimeOptions,
      el: hostRef.current,
    });
  }, [config, loading, surface, slug]);

  useEffect(
    () => () => {
      instanceRef.current?.destroy();
      instanceRef.current = null;
    },
    [],
  );

  const handleAvatarSelect = useCallback((preset: AvatarPreset) => {
    setSelectedAvatar(preset);
    localStorage.setItem(AVATAR_STORAGE_KEY, JSON.stringify(preset));
    setPickerOpen(false);
  }, []);

  const resolved = config ?? DEFAULT_COMMUNITY_CONFIG;
  const hasServer = resolved.serverURL.trim().length > 0;
  const presets = resolved.avatarPresets ?? [];

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
    <div className="aerisun-waline-wrap" style={{ position: "relative" }}>
      {/* Avatar selector trigger — small circle above the editor */}
      {presets.length > 0 && (
        <div className="aerisun-avatar-trigger-row">
          <button
            type="button"
            className="aerisun-avatar-trigger"
            title="点击选择头像"
            onClick={() => setPickerOpen((v) => !v)}
          >
            {selectedAvatar ? (
              <img src={selectedAvatar.avatar_url} alt={selectedAvatar.label} />
            ) : (
              <span className="aerisun-avatar-trigger__placeholder">?</span>
            )}
          </button>
          <span className="aerisun-avatar-trigger__hint">
            {selectedAvatar ? selectedAvatar.label : "选择头像"}
          </span>
        </div>
      )}
      {pickerOpen && presets.length > 0 && (
        <AvatarPicker
          presets={presets}
          onSelect={handleAvatarSelect}
          onClose={() => setPickerOpen(false)}
        />
      )}
      <div
        ref={hostRef}
        className={`aerisun-waline-host ${className ?? ""}`.trim()}
      />
    </div>
  );
};

export default WalineSurface;
