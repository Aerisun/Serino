import { Input } from "@/components/ui/Input";
import { cn } from "@/lib/utils";

interface AutoTitleFieldProps {
  value: string;
  onChange: (value: string) => void;
  isAuto: boolean;
  onAutoChange: (value: boolean) => void;
  switchLabel: string;
  inputLabel: string;
  placeholder?: string;
  required?: boolean;
}

export function AutoTitleField({
  value,
  onChange,
  isAuto,
  onAutoChange,
  switchLabel,
  inputLabel,
  placeholder,
  required = false,
}: AutoTitleFieldProps) {
  return (
    <div className="flex min-w-0 items-center">
      <div className="flex shrink-0 items-center gap-3">
        <span className="text-sm font-medium tracking-tight text-foreground/92">
          {switchLabel}
        </span>
        <button
          type="button"
          role="switch"
          aria-checked={isAuto}
          aria-label={switchLabel}
          onClick={() => onAutoChange(!isAuto)}
          className={cn(
            "relative inline-flex h-8 w-14 shrink-0 items-center rounded-full border transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-300/70 focus-visible:ring-offset-2",
            isAuto
              ? "border-primary/45 bg-primary shadow-[inset_0_1px_0_rgba(255,255,255,0.18)]"
              : "border-border/70 bg-muted/70",
          )}
        >
          <span
            className={cn(
              "pointer-events-none relative z-10 block h-6 w-6 rounded-full bg-white shadow-[0_8px_18px_rgba(15,23,42,0.18)] ring-1 ring-black/5 transition-transform duration-200 before:absolute before:inset-[0.15rem] before:rounded-full before:bg-gradient-to-br before:from-white/90 before:to-white/35 before:content-[''] dark:bg-slate-100 dark:ring-white/10 dark:before:from-white/45 dark:before:to-white/10",
              isAuto ? "translate-x-6" : "translate-x-1",
            )}
          />
        </button>
      </div>
      <div
        className={cn(
          "min-w-0 overflow-hidden transition-[max-width,opacity,margin] duration-200 ease-in-out",
          isAuto
            ? "ml-0 max-w-0 flex-[0_1_0] opacity-0"
            : "ml-5 max-w-[44rem] flex-1 opacity-100",
        )}
      >
        <Input
          value={value}
          onChange={(event) => onChange(event.target.value)}
          placeholder={placeholder}
          readOnly={isAuto}
          required={!isAuto && required}
          aria-label={inputLabel}
          tabIndex={isAuto ? -1 : undefined}
          className={cn(
            "h-10 min-h-10",
            isAuto && "cursor-default bg-muted/35 text-muted-foreground",
          )}
        />
      </div>
    </div>
  );
}
