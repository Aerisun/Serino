import { useState, useEffect, type ReactNode } from "react";
import { Calendar } from "lucide-react";
import { Input } from "@/components/ui/Input";
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

export function PublishTimeFooter({
  value,
  onChange,
  deleteButton,
  label: _label = "Published At",
  isCustom = false,
  onCustomChange,
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

  const handleCalendarClick = () => {
    // 触发输入框的日期选择器打开
    const input = document.querySelector(
      '[data-publish-time-input]'
    ) as HTMLInputElement;
    if (input) {
      input.showPicker?.();
    }
  };

  return (
    <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
      {/* 删除按钮 */}
      {deleteButton}
      
      {/* 发布时间控制组 - 右对齐，开关永远在最右边 */}
      <div className="flex items-center gap-3 ml-auto">
        {/* 自定义时间输入和日历图标 */}
        {isCustom && (
          <div className="flex items-center gap-1">
            {/* 日历图标按钮 */}
            <button
              type="button"
              onClick={handleCalendarClick}
              className="flex-shrink-0 p-1.5 rounded-lg hover:bg-muted transition-colors"
              aria-label="Open date picker"
            >
              <Calendar className="h-4 w-4 text-muted-foreground" />
            </button>

            {/* 日期时间输入 */}
            <Input
              data-publish-time-input
              type="datetime-local"
              value={inputValue}
              onChange={handleInputChange}
              onBlur={handleInputBlur}
              className={cn(
                "h-9 w-48 rounded-lg text-sm px-2",
                hasInteracted && !isValidFormat
                  ? "border-red-500 focus:border-red-500 focus:ring-red-200"
                  : "border-border/60 bg-background/90"
              )}
              placeholder="YYYY-MM-DD HH:mm"
            />
          </div>
        )}

        {/* 标签和切换开关 - 开关始终在最右边 */}
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium whitespace-nowrap">
            {isCustom ? "自定义" : "默认发布时间为当前时间，开启开关可自定义"}
          </span>
          
          {/* 自定义切换开关 */}
          <button
            type="button"
            onClick={handleToggleCustom}
            className={cn(
              "relative inline-flex h-5 w-9 flex-shrink-0 items-center rounded-full border transition-colors",
              isCustom
                ? "border-primary/55 bg-primary"
                : "border-border/70 bg-muted"
            )}
            aria-label="Toggle custom publish time"
          >
            <span
              className={cn(
                "inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform",
                isCustom ? "translate-x-4" : "translate-x-1"
              )}
            />
          </button>
        </div>
      </div>

      {/* 格式错误提示（显示在下方） */}
      {hasInteracted && !isValidFormat && inputValue && (
        <div className="text-xs text-red-500 col-span-full">
          格式错误，请使用 YYYY-MM-DD HH:mm
        </div>
      )}
    </div>
  );
}
