import { cn } from "@/lib/utils";

interface AppleSwitchProps {
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
  label?: string;
  description?: string;
  className?: string;
  disabled?: boolean;
}

export function AppleSwitch({
  checked,
  onCheckedChange,
  label,
  description,
  className,
  disabled = false,
}: AppleSwitchProps) {
  return (
    <div
      className={cn(
        "flex items-center justify-between gap-4 rounded-2xl border border-white/45 bg-white/65 px-4 py-3 shadow-[0_14px_34px_rgba(15,23,42,0.05)] backdrop-blur-xl transition-colors hover:bg-white/75 dark:border-white/10 dark:bg-white/[0.04] dark:hover:bg-white/[0.06]",
        disabled && "cursor-not-allowed opacity-60",
        className,
      )}
    >
      {label || description ? (
        <div className="min-w-0 space-y-1">
          {label ? (
            <div className="text-sm font-medium tracking-tight text-foreground/92">
              {label}
            </div>
          ) : null}
          {description ? (
            <div className="text-xs leading-5 text-muted-foreground">
              {description}
            </div>
          ) : null}
        </div>
      ) : null}

      <button
        type="button"
        role="switch"
        aria-checked={checked}
        onClick={() => onCheckedChange(!checked)}
        disabled={disabled}
        className={cn(
          "relative inline-flex h-8 w-14 shrink-0 items-center overflow-hidden rounded-full border transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
          checked
            ? "border-sky-400/45 bg-gradient-to-r from-sky-500/35 via-cyan-400/25 to-emerald-400/25 shadow-[inset_0_1px_0_rgba(255,255,255,0.24),0_0_0_1px_rgba(56,189,248,0.14),0_10px_28px_rgba(14,165,233,0.12)]"
            : "border-slate-400/25 bg-slate-500/12 shadow-[inset_0_1px_0_rgba(255,255,255,0.14),0_0_0_1px_rgba(148,163,184,0.08)]",
          disabled && "pointer-events-none",
        )}
      >
        <span
          className={cn(
            "pointer-events-none relative block h-6 w-6 rounded-full bg-white shadow-[0_8px_18px_rgba(15,23,42,0.18)] ring-1 ring-black/5 transition-transform duration-200 before:absolute before:inset-[0.15rem] before:rounded-full before:bg-gradient-to-br before:from-white/90 before:to-white/35 before:content-[''] dark:bg-slate-100 dark:ring-white/10 dark:before:from-white/45 dark:before:to-white/10",
            checked ? "translate-x-6" : "translate-x-1",
          )}
        />
      </button>
    </div>
  );
}
