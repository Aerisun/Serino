import { Check, LockKeyhole } from "lucide-react";
import type { AvatarPreset } from "@/lib/community-config";
import {
  communityPopupClass,
  fallbackAvatar,
  type DraftState,
} from "./waline-types";

export interface WalineAvatarSelectorProps {
  avatarPresets: AvatarPreset[];
  selectedAvatarKey: string;
  draftName: string;
  isAvatarOccupied: (preset: AvatarPreset) => boolean;
  open: boolean;
  onSelect: (field: keyof DraftState, value: string) => void;
  onClose: () => void;
  onToggle: () => void;
  selectedPreset: AvatarPreset | null;
}

const WalineAvatarSelector = ({
  avatarPresets,
  selectedAvatarKey,
  draftName,
  isAvatarOccupied,
  open,
  onSelect,
  onClose,
  onToggle,
  selectedPreset,
}: WalineAvatarSelectorProps) => (
  <>
    <div className="self-end">
      <button
        type="button"
        onClick={onToggle}
        className="group relative inline-flex h-14 w-14 shrink-0 items-center justify-center overflow-hidden rounded-full border border-[rgb(var(--shiro-border-rgb)/0.22)] bg-card/[0.9] p-1.5 shadow-[0_14px_36px_rgb(15_23_42/0.08)] transition hover:border-[rgb(var(--shiro-accent-rgb)/0.28)] hover:shadow-[0_18px_40px_rgb(15_23_42/0.12)] dark:border-[rgb(var(--shiro-border-rgb)/0.28)] dark:bg-card/[0.96]"
        aria-expanded={open}
        aria-label="打开头像库"
      >
        <img
          src={selectedPreset?.avatar_url || fallbackAvatar(draftName)}
          alt={selectedPreset?.label || draftName || "当前头像"}
          className="h-full w-full rounded-full object-cover"
        />
        <span className="absolute inset-0 rounded-full ring-1 ring-black/5 ring-inset dark:ring-white/10" />
      </button>
    </div>

    {open ? (
      <div className="pointer-events-none absolute left-0 top-[calc(100%+0.8rem)] z-20 w-[18.5rem] max-w-[calc(100vw-4rem)] md:w-[20rem]">
        <div className={`pointer-events-auto rounded-[1.35rem] p-4 shadow-[0_28px_70px_rgb(15_23_42/0.16)] ${communityPopupClass}`}>
          <div className="grid grid-cols-4 gap-3">
            {avatarPresets.map((preset) => {
              const occupied = isAvatarOccupied(preset);
              const selected = selectedAvatarKey === preset.key;
              const locked = occupied && !selected;
              return (
                <button
                  key={preset.key}
                  type="button"
                  title={locked ? `${preset.label} 已被占用` : preset.label}
                  disabled={locked}
                  aria-disabled={locked}
                  onClick={() => {
                    onSelect("avatarKey", preset.key);
                    onClose();
                  }}
                  className={[
                    "group relative rounded-full border p-1 transition",
                    selected
                      ? "border-[rgb(var(--shiro-accent-rgb)/0.38)] bg-[rgb(var(--shiro-accent-rgb)/0.1)] shadow-[0_12px_28px_rgb(var(--shiro-accent-rgb)/0.14)]"
                      : "border-[rgb(var(--shiro-border-rgb)/0.14)] bg-card/[0.84] hover:border-[rgb(var(--shiro-accent-rgb)/0.22)] dark:bg-card/[0.92]",
                    locked ? "cursor-not-allowed opacity-45 grayscale-[0.2] saturate-50" : "",
                  ].join(" ")}
                >
                  <img
                    src={preset.avatar_url}
                    alt={preset.label}
                    className={`h-12 w-12 rounded-full object-cover shadow-sm md:h-14 md:w-14 ${locked ? "opacity-80" : ""}`}
                    loading="lazy"
                  />
                  {selected ? (
                    <span className="absolute -right-0.5 -top-0.5 inline-flex h-5 w-5 items-center justify-center rounded-full bg-[rgb(var(--shiro-accent-rgb)/0.92)] text-white shadow-sm">
                      <Check className="h-3 w-3" />
                    </span>
                  ) : null}
                  {locked ? (
                    <span className="absolute inset-0 flex items-center justify-center rounded-full bg-black/32 text-white/92 shadow-sm backdrop-blur-[1px]">
                      <LockKeyhole className="h-3 w-3" />
                    </span>
                  ) : null}
                </button>
              );
            })}
          </div>
        </div>
      </div>
    ) : null}
  </>
);

export default WalineAvatarSelector;
