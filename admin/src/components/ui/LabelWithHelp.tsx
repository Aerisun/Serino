import {
  useCallback,
  useEffect,
  useId,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { createPortal } from "react-dom";
import { CircleHelp } from "lucide-react";
import { Label } from "@/components/ui/Label";
import { cn } from "@/lib/utils";

interface LabelWithHelpProps {
  label: ReactNode;
  htmlFor?: string;
  title?: ReactNode;
  description: ReactNode;
  usageTitle?: ReactNode;
  usageItems?: ReactNode[];
  className?: string;
}

const PANEL_MARGIN = 16;
const PANEL_OFFSET = 4;
const PANEL_MAX_WIDTH = 352;
const PANEL_MAX_HEIGHT = 520;
const PANEL_VERTICAL_PADDING = 32;
const AUTO_CLOSE_DELAY_MS = 1500;

export function LabelWithHelp({
  label,
  htmlFor,
  title,
  description,
  usageTitle,
  usageItems = [],
  className,
}: LabelWithHelpProps) {
  const [open, setOpen] = useState(false);
  const [panelStyle, setPanelStyle] = useState<{
    top: number;
    left: number;
    width: number;
    maxHeight: number;
    placement: "above" | "below";
  } | null>(null);
  const triggerRef = useRef<HTMLButtonElement | null>(null);
  const panelRef = useRef<HTMLDivElement | null>(null);
  const closeTimerRef = useRef<number | null>(null);
  const panelId = useId();
  const contentMaxHeight = Math.max(
    160,
    (panelStyle?.maxHeight ?? PANEL_MAX_HEIGHT) - PANEL_VERTICAL_PADDING,
  );

  const clearCloseTimer = useCallback(() => {
    if (closeTimerRef.current !== null) {
      window.clearTimeout(closeTimerRef.current);
      closeTimerRef.current = null;
    }
  }, []);

  const scheduleClose = useCallback(() => {
    if (closeTimerRef.current !== null) {
      return;
    }
    closeTimerRef.current = window.setTimeout(() => {
      setOpen(false);
      closeTimerRef.current = null;
    }, AUTO_CLOSE_DELAY_MS);
  }, []);

  const updatePosition = useCallback(() => {
    if (!triggerRef.current) {
      return;
    }

    const triggerRect = triggerRef.current.getBoundingClientRect();
    const availableRight = Math.max(
      120,
      window.innerWidth - triggerRect.right - PANEL_MARGIN - PANEL_OFFSET,
    );
    const width = Math.min(PANEL_MAX_WIDTH, availableRight);
    const panelHeight = panelRef.current?.getBoundingClientRect().height ?? 0;
    const desiredHeight = panelHeight || PANEL_MAX_HEIGHT;
    const availableBelow = window.innerHeight - triggerRect.bottom - PANEL_MARGIN;
    const availableAbove = triggerRect.top - PANEL_MARGIN;
    const openAbove = availableBelow < desiredHeight && availableAbove > PANEL_MARGIN;
    const availableHeight = Math.max(160, openAbove ? availableAbove : availableBelow);
    const maxHeight = Math.min(PANEL_MAX_HEIGHT, availableHeight);
    const effectiveHeight = Math.min(desiredHeight, maxHeight);
    const nextTop = openAbove
      ? Math.max(PANEL_MARGIN, triggerRect.top - PANEL_OFFSET - effectiveHeight)
      : Math.min(
          triggerRect.bottom + PANEL_OFFSET,
          window.innerHeight - effectiveHeight - PANEL_MARGIN,
        );

    setPanelStyle({
      left: triggerRect.right + PANEL_OFFSET,
      top: Math.max(PANEL_MARGIN, nextTop),
      width,
      maxHeight,
      placement: openAbove ? "above" : "below",
    });
  }, []);

  useEffect(() => {
    if (!open) {
      clearCloseTimer();
      setPanelStyle(null);
      return;
    }

    const handlePointerDown = (event: MouseEvent) => {
      const target = event.target as Node;
      if (
        panelRef.current?.contains(target) ||
        triggerRef.current?.contains(target)
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

    const handleWindowChange = () => {
      updatePosition();
    };

    document.addEventListener("mousedown", handlePointerDown);
    document.addEventListener("keydown", handleEscape);
    window.addEventListener("resize", handleWindowChange);
    window.addEventListener("scroll", handleWindowChange, true);
    updatePosition();
    const rafId = window.requestAnimationFrame(() => {
      updatePosition();
    });

    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
      document.removeEventListener("keydown", handleEscape);
      window.removeEventListener("resize", handleWindowChange);
      window.removeEventListener("scroll", handleWindowChange, true);
      window.cancelAnimationFrame(rafId);
    };
  }, [clearCloseTimer, open, scheduleClose, updatePosition]);

  useEffect(() => {
    return () => {
      clearCloseTimer();
    };
  }, [clearCloseTimer]);

  return (
    <div className={cn("flex items-center gap-2", className)}>
      <Label htmlFor={htmlFor}>{label}</Label>
      <div className="relative">
        <button
          ref={triggerRef}
          type="button"
          className={cn(
            "inline-flex h-5 w-5 items-center justify-center rounded-full border border-border/60 text-muted-foreground transition-colors",
            "hover:border-border hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50",
          )}
          aria-label="查看字段说明"
          aria-expanded={open}
          aria-controls={panelId}
          onClick={() => {
            clearCloseTimer();
            setOpen((current) => !current);
          }}
          onMouseEnter={clearCloseTimer}
          onMouseLeave={() => {
            if (open) {
              scheduleClose();
            }
          }}
        >
          <CircleHelp className="h-3.5 w-3.5" />
        </button>
      </div>

      {open && typeof document !== "undefined"
        ? createPortal(
            <div
              ref={panelRef}
              id={panelId}
              role="dialog"
              aria-live="polite"
              onMouseEnter={clearCloseTimer}
              onMouseLeave={scheduleClose}
              style={
                panelStyle
                  ? {
                      top: panelStyle.top,
                      left: panelStyle.left,
                      width: panelStyle.width,
                      maxHeight: panelStyle.maxHeight,
                    }
                  : undefined
              }
              className={cn(
                "fixed z-[160] origin-top-left overflow-hidden rounded-2xl border border-border bg-background p-4 shadow-[0_22px_56px_rgba(15,23,42,0.16)]",
                panelStyle?.placement === "above" && "origin-bottom-left",
                "transition-[opacity,transform] duration-150 ease-out",
                panelStyle ? "opacity-100 scale-100" : "opacity-0 scale-95",
              )}
            >
              <div
                className={cn(
                  "pointer-events-none absolute left-4 h-2 w-2 rounded-full border border-border bg-background shadow-sm",
                  panelStyle?.placement === "above"
                    ? "bottom-0 translate-y-1/2"
                    : "top-0 -translate-y-1/2",
                )}
              />
              <div
                className="space-y-3 overflow-y-auto overscroll-contain pr-1 text-left"
                style={{ maxHeight: contentMaxHeight }}
              >
                {title ? (
                  <p className="pr-4 text-sm font-semibold text-foreground">{title}</p>
                ) : null}
                <p className="text-xs leading-5 text-foreground/80">{description}</p>
                {usageItems.length ? (
                  <div className="space-y-2">
                    {usageTitle ? (
                      <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-foreground/72">
                        {usageTitle}
                      </p>
                    ) : null}
                    <ul className="space-y-1 text-xs leading-5 text-foreground/74">
                      {usageItems.map((item, index) => (
                        <li key={index} className="flex gap-2">
                          <span className="mt-[0.4rem] h-1 w-1 rounded-full bg-foreground/50" />
                          <span>{item}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : null}
              </div>
            </div>,
            document.body,
          )
        : null}
    </div>
  );
}
