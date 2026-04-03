import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { createPortal } from "react-dom";
import { ChevronDown, Loader2, Sparkles, X } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Label } from "@/components/ui/Label";
import { Textarea } from "@/components/ui/Textarea";
import { cn } from "@/lib/utils";

interface AiActionClusterProps {
  actionLabel: string;
  detailLabel?: string;
  onAction: (detail?: string) => Promise<void> | void;
  loading?: boolean;
  disabled?: boolean;
  className?: string;
  showDetailTrigger?: boolean;
  detailValue?: string;
  onDetailChange?: (value: string) => void;
  detailTitle?: ReactNode;
  detailDescription?: ReactNode;
  detailPlaceholder?: string;
  submitLabel?: string;
  clearLabel?: string;
  closeLabel?: string;
  responseTitle?: ReactNode;
  responseValue?: string | null;
  responsePlaceholder?: string;
  responseRows?: number;
  responseEditable?: boolean;
  showResponseWhenEmpty?: boolean;
  onResponseChange?: (value: string) => void;
  closeOnPromptAction?: boolean;
}

type PanelStyle = {
  top: number;
  left: number;
  width: number;
};

const PANEL_MARGIN = 16;
const PANEL_OFFSET = 14;
const PANEL_MAX_WIDTH = 420;
const PANEL_MIN_WIDTH = 300;

export function AiActionCluster({
  actionLabel,
  detailLabel,
  onAction,
  loading = false,
  disabled = false,
  className,
  showDetailTrigger = false,
  detailValue = "",
  onDetailChange,
  detailTitle,
  detailDescription,
  detailPlaceholder,
  submitLabel = "执行",
  clearLabel = "清空",
  closeLabel = "关闭",
  responseTitle,
  responseValue,
  responsePlaceholder,
  responseRows = 3,
  responseEditable = false,
  showResponseWhenEmpty = false,
  onResponseChange,
  closeOnPromptAction = false,
}: AiActionClusterProps) {
  const shellRef = useRef<HTMLDivElement | null>(null);
  const panelRef = useRef<HTMLDivElement | null>(null);
  const [open, setOpen] = useState(false);
  const [panelStyle, setPanelStyle] = useState<PanelStyle | null>(null);
  const hasDetailTrigger = showDetailTrigger;
  const hasPrompt = detailValue.trim().length > 0;
  const hasResponse = Boolean(responseValue && responseValue.trim().length > 0);
  const shouldShowResponse = Boolean(responseTitle) && (responseEditable || showResponseWhenEmpty || hasResponse);

  const updatePosition = useCallback(() => {
    if (!shellRef.current) {
      return;
    }

    const triggerRect = shellRef.current.getBoundingClientRect();
    const availableWidth = Math.max(
      PANEL_MIN_WIDTH,
      Math.min(PANEL_MAX_WIDTH, window.innerWidth - PANEL_MARGIN * 2),
    );
    const nextLeft = Math.min(
      Math.max(PANEL_MARGIN, triggerRect.right - availableWidth),
      window.innerWidth - availableWidth - PANEL_MARGIN,
    );
    const panelHeight = panelRef.current?.getBoundingClientRect().height ?? 0;
    const desiredHeight = Math.max(panelHeight, 260);
    const availableBelow = window.innerHeight - triggerRect.bottom - PANEL_MARGIN;
    const openAbove = availableBelow < desiredHeight && triggerRect.top > desiredHeight + PANEL_MARGIN;
    const nextTop = openAbove
      ? Math.max(PANEL_MARGIN, triggerRect.top - desiredHeight - PANEL_OFFSET)
      : Math.min(
          triggerRect.bottom + PANEL_OFFSET,
          window.innerHeight - desiredHeight - PANEL_MARGIN,
        );

    setPanelStyle({
      top: nextTop,
      left: nextLeft,
      width: availableWidth,
    });
  }, []);

  useEffect(() => {
    if (!open) {
      setPanelStyle(null);
      return;
    }

    const handlePointerDown = (event: MouseEvent) => {
      const target = event.target as Node;
      if (
        shellRef.current?.contains(target) ||
        panelRef.current?.contains(target)
      ) {
        return;
      }
      setOpen(false);
    };

    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setOpen(false);
      }
    };

    const handleViewportChange = () => {
      updatePosition();
    };

    document.addEventListener("mousedown", handlePointerDown);
    document.addEventListener("keydown", handleEscape);
    window.addEventListener("resize", handleViewportChange);
    window.addEventListener("scroll", handleViewportChange, true);
    updatePosition();
    const rafId = window.requestAnimationFrame(() => {
      updatePosition();
    });

    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
      document.removeEventListener("keydown", handleEscape);
      window.removeEventListener("resize", handleViewportChange);
      window.removeEventListener("scroll", handleViewportChange, true);
      window.cancelAnimationFrame(rafId);
    };
  }, [open, updatePosition]);

  useEffect(() => {
    if (!open) {
      return;
    }
    updatePosition();
  }, [detailValue, hasResponse, open, responseValue, shouldShowResponse, updatePosition]);

  const handlePrimaryAction = async () => {
    await onAction(hasPrompt ? detailValue : undefined);
  };

  const handlePromptAction = async () => {
    await onAction(detailValue.trim() || undefined);
    if (closeOnPromptAction) {
      setOpen(false);
    }
  };

  return (
    <div ref={shellRef} className={cn("relative inline-flex shrink-0", className)}>
      <div
        className={cn(
          "group relative inline-flex items-center gap-[0.18rem] rounded-[1.3rem] border border-[rgba(255,255,255,0.85)] bg-[linear-gradient(145deg,rgba(255,255,255,0.98),rgba(245,248,255,0.94)_52%,rgba(239,244,255,0.9)_100%)] px-[0.26rem] py-[0.18rem] shadow-[0_12px_24px_rgba(15,23,42,0.065)] ring-1 ring-[rgba(148,163,184,0.08)] backdrop-blur-[22px] dark:border-white/12 dark:bg-[linear-gradient(145deg,rgba(30,41,59,0.96),rgba(15,23,42,0.94)_52%,rgba(12,18,32,0.96)_100%)] dark:ring-white/5",
          hasDetailTrigger ? "pr-[0.22rem]" : "pr-[0.26rem]",
        )}
      >
        <span className="pointer-events-none absolute inset-[1px] rounded-[inherit] border border-white/55 opacity-80 dark:border-white/8" />
        <span className="pointer-events-none absolute left-[0.82rem] top-[calc(100%-0.43rem)] h-1.5 w-1.5 rounded-full bg-[radial-gradient(circle_at_30%_30%,rgba(96,165,250,1),rgba(59,130,246,0.92))] shadow-[0_0_0_2px_rgba(255,255,255,0.76),0_4px_8px_rgba(59,130,246,0.18)] dark:shadow-[0_0_0_2px_rgba(15,23,42,0.86),0_4px_8px_rgba(59,130,246,0.25)]" />

        <Button
          type="button"
          variant="ghost"
          size="icon"
          className={cn(
            "group/ai relative min-h-0 h-8 w-8 rounded-[0.95rem] border-none bg-transparent p-0 text-slate-700 shadow-none transition-[transform,background-color,color] hover:-translate-y-[1px] hover:bg-white/55 hover:text-slate-900 dark:text-slate-100 dark:hover:bg-white/[0.06] dark:hover:text-white",
            !hasDetailTrigger && "h-[1.85rem] w-[1.85rem]",
          )}
          onClick={() => void handlePrimaryAction()}
          disabled={disabled || loading}
          aria-label={actionLabel}
          title={actionLabel}
        >
          {loading ? (
            <Loader2 className="h-[0.92rem] w-[0.92rem] shrink-0 animate-spin" />
          ) : (
            <Sparkles className="h-[0.92rem] w-[0.92rem] shrink-0 transition-transform duration-200 group-hover/ai:scale-110 group-hover/ai:rotate-6" />
          )}
        </Button>

        {hasDetailTrigger ? (
          <>
            <div className="h-[1.35rem] w-px rounded-full bg-[linear-gradient(180deg,rgba(203,213,225,0),rgba(203,213,225,0.88),rgba(203,213,225,0))] dark:bg-[linear-gradient(180deg,rgba(148,163,184,0),rgba(148,163,184,0.34),rgba(148,163,184,0))]" />
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="group/expand relative min-h-0 h-8 w-[1.8rem] rounded-[0.95rem] border-none bg-transparent p-0 text-slate-500 shadow-none transition-[transform,background-color,color] hover:-translate-y-[1px] hover:bg-white/45 hover:text-slate-700 dark:text-slate-300 dark:hover:bg-white/[0.05] dark:hover:text-white"
              onClick={() => setOpen((current) => !current)}
              disabled={disabled || loading}
              aria-label={detailLabel ?? actionLabel}
              title={detailLabel ?? actionLabel}
              aria-expanded={open}
            >
              <ChevronDown className={cn("h-[0.92rem] w-[0.92rem] shrink-0 transition-transform duration-200 group-hover/expand:scale-105", open && "rotate-180")} />
            </Button>
          </>
        ) : null}
      </div>

      {open && typeof document !== "undefined"
        ? createPortal(
            <div
              ref={panelRef}
              role="dialog"
              aria-live="polite"
              className={cn(
                "fixed z-[170] overflow-hidden rounded-[1.65rem] border border-[rgba(var(--admin-border-strong)/0.08)] bg-[linear-gradient(165deg,rgba(255,255,255,0.96),rgba(247,250,255,0.92)_48%,rgba(239,246,255,0.92)_100%)] shadow-[0_30px_70px_rgba(15,23,42,0.16)] backdrop-blur-[24px] transition-[opacity,transform] duration-200 dark:bg-[linear-gradient(165deg,rgba(30,41,59,0.96),rgba(15,23,42,0.94)_50%,rgba(12,18,32,0.96)_100%)]",
                panelStyle ? "opacity-100 translate-y-0 scale-100" : "opacity-0 translate-y-2 scale-[0.98]",
              )}
              style={panelStyle ?? undefined}
            >
              <div className="pointer-events-none absolute inset-x-6 top-0 h-20 rounded-full bg-[radial-gradient(circle_at_top,rgba(14,165,233,0.2),rgba(255,255,255,0))]" />
              <div className="relative space-y-4 p-5">
                <div className="flex items-start justify-between gap-4">
                  <div className="space-y-1.5">
                    {detailTitle ? (
                      <div className="flex items-center gap-2 text-sm font-semibold text-foreground">
                        <span className="inline-flex h-8 w-8 items-center justify-center rounded-[0.95rem] bg-[radial-gradient(circle_at_30%_30%,rgba(14,165,233,0.14),rgba(59,130,246,0.08))] text-sky-600 dark:text-sky-300">
                          <Sparkles className="h-4 w-4" />
                        </span>
                        <span>{detailTitle}</span>
                      </div>
                    ) : null}
                    {detailDescription ? (
                      <p className="max-w-[30rem] text-xs leading-5 text-muted-foreground/95">
                        {detailDescription}
                      </p>
                    ) : null}
                  </div>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="h-9 w-9 rounded-full text-muted-foreground"
                    onClick={() => setOpen(false)}
                    aria-label={closeLabel}
                    title={closeLabel}
                  >
                    <X className="h-4 w-4" />
                  </Button>
                </div>

                <div className="space-y-2">
                  <Label className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground/85">
                    {detailLabel ?? actionLabel}
                  </Label>
                  <Textarea
                    value={detailValue}
                    onChange={(event) => onDetailChange?.(event.target.value)}
                    rows={4}
                    className="min-h-[118px] resize-y rounded-[1.2rem] border-white/45 bg-[rgb(var(--admin-surface-strong)/0.64)] pr-4 text-sm leading-6 shadow-[inset_0_1px_0_rgba(255,255,255,0.34)]"
                    placeholder={detailPlaceholder}
                    disabled={disabled || loading}
                  />
                </div>

                {shouldShowResponse ? (
                  <div className="space-y-2">
                    <Label className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground/85">
                      {responseTitle}
                    </Label>
                    {responseEditable ? (
                      <Textarea
                        value={responseValue ?? ""}
                        onChange={(event) => onResponseChange?.(event.target.value)}
                        rows={responseRows}
                        className="min-h-[96px] resize-y rounded-[1.2rem] border-white/45 bg-[rgb(var(--admin-surface-strong)/0.64)] pr-4 text-sm leading-6 shadow-[inset_0_1px_0_rgba(255,255,255,0.34)]"
                        placeholder={responsePlaceholder}
                      />
                    ) : (
                      <div className="rounded-[1.2rem] border border-[rgba(var(--admin-border-strong)/0.08)] bg-[rgb(var(--admin-surface-strong)/0.58)] px-4 py-3 text-sm leading-7 text-foreground shadow-[inset_0_1px_0_rgba(255,255,255,0.28)]">
                        {responseValue}
                      </div>
                    )}
                  </div>
                ) : null}

                <div className="flex items-center justify-between gap-3">
                  <Button
                    type="button"
                    variant="ghost"
                    className="h-10 rounded-full px-4 text-muted-foreground"
                    onClick={() => onDetailChange?.("")}
                    disabled={disabled || loading || !hasPrompt}
                  >
                    {clearLabel}
                  </Button>
                  <Button
                    type="button"
                    variant="glass"
                    className="h-10 rounded-full px-5 text-foreground shadow-[0_16px_32px_rgba(14,165,233,0.14)]"
                    onClick={() => void handlePromptAction()}
                    disabled={disabled || loading}
                  >
                    {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Sparkles className="mr-2 h-4 w-4 text-sky-500" />}
                    {submitLabel}
                  </Button>
                </div>
              </div>
            </div>,
            document.body,
          )
        : null}
    </div>
  );
}
