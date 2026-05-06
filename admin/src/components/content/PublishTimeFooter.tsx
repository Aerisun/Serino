import { useState, useEffect, type ReactNode } from "react";
import { Calendar } from "lucide-react";
import { LabelWithHelp } from "@/components/ui/LabelWithHelp";
import { cn } from "@/lib/utils";
import {
  datetimeLocalInBeijingToIso,
  getCurrentBeijingIsoString,
  isValidBeijingDatetimeLocal,
  isoToDatetimeLocalInBeijing,
} from "@/lib/time";

interface PublishTimeFooterProps {
  /** 发布时间值（ISO 字符串） */
  value: string | null;
  /** 发布时间改变回调 */
  onChange: (value: string | null) => void;
  /** 要显示的删除按钮 */
  deleteButton?: ReactNode;
  /** 发布时间标签 */
  label?: string;
  /** 是否使用自定义时间 */
  isCustom?: boolean;
  /** 自定义时间改变回调 */
  onCustomChange?: (isCustom: boolean) => void;
  className?: string;
}

// 验证时间格式
const isValidDateFormat = (value: string): boolean => {
  return isValidBeijingDatetimeLocal(value);
};

/** 将 ISO 字符串转换为 datetime-local 格式 */
const isoToDatetimeLocal = (isoString: string | null): string => {
  return isoToDatetimeLocalInBeijing(isoString);
};

/** 将 datetime-local 值转换为 ISO 字符串 */
const datetimeLocalToIso = (value: string): string => {
  return datetimeLocalInBeijingToIso(value);
};

const formatDatetimeLocalLabel = (value: string): string => {
  const matched = value.match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})$/);
  if (!matched) {
    return "调整时间";
  }

  const [, year, month, day, hour, minute] = matched;
  return `${year}/${month}/${day} ${hour}:${minute}`;
};

export function PublishTimeFooter({
  value,
  onChange,
  deleteButton,
  label: _label = "Published At",
  isCustom = false,
  onCustomChange,
  className,
}: PublishTimeFooterProps) {
  const [inputValue, setInputValue] = useState(isoToDatetimeLocal(value));
  const [isValidFormat, setIsValidFormat] = useState(true);
  const [hasInteracted, setHasInteracted] = useState(false);

  // 当使用自定义时间时，同步输入值
  useEffect(() => {
    if (isCustom && value) {
      const datetimeLocalValue = isoToDatetimeLocal(value);
      setInputValue(datetimeLocalValue);
    }
  }, [isCustom, value]);

  const handleToggleCustom = () => {
    const newIsCustom = !isCustom;
    onCustomChange?.(newIsCustom);

    if (!newIsCustom) {
      // 切换到"当前时间"，清除自定义时间
      onChange(null);
      setInputValue("");
      setIsValidFormat(true);
      setHasInteracted(false);
    } else {
      // 切换到"自定义"，使用当前时间
      const now = getCurrentBeijingIsoString();
      onChange(now);
      setInputValue(isoToDatetimeLocal(now));
      setIsValidFormat(true);
    }
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newValue = e.target.value;
    setInputValue(newValue);

    if (newValue) {
      // 实时验证格式
      const isValid = isValidDateFormat(newValue);
      setIsValidFormat(isValid);

      if (isValid) {
        onChange(datetimeLocalToIso(newValue));
      }
    } else {
      setIsValidFormat(true);
      onChange(null);
    }
  };

  const handleInputBlur = () => {
    setHasInteracted(true);

    if (inputValue && !isValidDateFormat(inputValue)) {
      setIsValidFormat(false);
    }
  };

  return (
    <div className={cn("space-y-2", className)}>
      <div className="flex min-w-0 items-center">
        {/* 标签和切换开关 */}
        <div className="flex shrink-0 items-center gap-3">
          <LabelWithHelp
            label="时间自定义"
            title="时间自定义"
            description={
              <>
                <span className="block">
                  关闭：发布时间使用保存时的当前时间
                </span>
                <span className="mt-1 block">
                  开启：点击右侧时间，手动选择发布时间
                </span>
              </>
            }
            className="gap-1.5 whitespace-nowrap [&>label]:tracking-tight [&>label]:text-foreground/92"
          />

          {/* 自定义切换开关 */}
          <button
            type="button"
            role="switch"
            aria-checked={isCustom}
            onClick={handleToggleCustom}
            className={cn(
              "relative inline-flex h-8 w-14 shrink-0 items-center rounded-full border transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-300/70 focus-visible:ring-offset-2",
              isCustom
                ? "border-primary/45 bg-primary shadow-[inset_0_1px_0_rgba(255,255,255,0.18)]"
                : "border-border/70 bg-muted/70",
            )}
            aria-label="Toggle custom publish time"
          >
            <span
              className={cn(
                "pointer-events-none relative z-10 block h-6 w-6 rounded-full bg-white shadow-[0_8px_18px_rgba(15,23,42,0.18)] ring-1 ring-black/5 transition-transform duration-200 before:absolute before:inset-[0.15rem] before:rounded-full before:bg-gradient-to-br before:from-white/90 before:to-white/35 before:content-[''] dark:bg-slate-100 dark:ring-white/10 dark:before:from-white/45 dark:before:to-white/10",
                isCustom ? "translate-x-6" : "translate-x-1",
              )}
            />
          </button>
        </div>

        {/* 自定义时间选择 */}
        <div
          className={cn(
            "min-w-0 overflow-hidden transition-[max-width,opacity,margin] duration-200 ease-in-out",
            isCustom
              ? "ml-3 max-w-[18rem] flex-1 opacity-100 sm:ml-5"
              : "ml-0 max-w-0 flex-[0_1_0] opacity-0",
          )}
        >
          <div
            className={cn(
              "relative flex h-10 min-h-10 min-w-0 items-center rounded-[var(--admin-radius-md)] admin-glass-input px-3 text-sm ring-offset-background transition-[border,box-shadow] focus-within:outline-none focus-within:ring-2 focus-within:ring-ring focus-within:ring-offset-2",
              hasInteracted && !isValidFormat
                ? "border-red-500 focus-within:border-red-500 focus-within:ring-red-200"
                : "border-border/60 bg-background/90",
            )}
          >
            <Calendar className="mr-2 h-4 w-4 shrink-0 text-muted-foreground/80" />
            <span className="min-w-0 flex-1 truncate whitespace-nowrap text-foreground">
              {formatDatetimeLocalLabel(inputValue)}
            </span>

            <input
              data-publish-time-input
              type="datetime-local"
              value={inputValue}
              onChange={handleInputChange}
              onBlur={handleInputBlur}
              onClick={(event) => event.currentTarget.showPicker?.()}
              className="absolute inset-0 h-full w-full cursor-pointer opacity-0"
              disabled={!isCustom}
              tabIndex={isCustom ? undefined : -1}
              aria-label="调整发布时间"
            />
          </div>
        </div>
      </div>

      {/* 格式错误提示（显示在下方） */}
      {hasInteracted && !isValidFormat && inputValue && (
        <div className="text-xs text-red-500">
          格式错误，请使用 YYYY-MM-DD HH:mm
        </div>
      )}

      {/* 删除按钮：独立留在右下角，不参与上方控制项横排 */}
      {deleteButton && (
        <div className="flex justify-end pt-1">{deleteButton}</div>
      )}
    </div>
  );
}
