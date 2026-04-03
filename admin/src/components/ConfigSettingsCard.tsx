import type { ReactNode } from "react";
import { AdminSurface } from "@/components/AdminSurface";
import { DirtySaveButton, PendingSaveBadge } from "@/components/ui/DirtySaveButton";
import { cn } from "@/lib/utils";

type ConfigStatusTone = "pending" | "available" | "invalid" | "checking";

interface ConfigSettingsCardProps {
  eyebrow?: ReactNode;
  title: ReactNode;
  description?: ReactNode;
  dirty: boolean;
  saving?: boolean;
  saveDisabled?: boolean;
  onSave: () => void;
  testAction?: ReactNode;
  statusIndicator?: {
    label: ReactNode;
    tone: ConfigStatusTone;
  };
  className?: string;
  contentClassName?: string;
  headerClassName?: string;
  children: ReactNode;
}

export function ConfigSettingsCard({
  eyebrow,
  title,
  description,
  dirty,
  saving = false,
  saveDisabled = false,
  onSave,
  testAction,
  statusIndicator,
  className,
  contentClassName,
  headerClassName,
  children,
}: ConfigSettingsCardProps) {
  return (
    <AdminSurface
      eyebrow={eyebrow}
      title={title}
      description={description}
      className={cn("w-full max-w-3xl", className)}
      contentClassName={contentClassName}
      headerClassName={headerClassName}
      actions={(
        <>
          {dirty ? <PendingSaveBadge /> : null}
          {statusIndicator ? (
            <ConfigCardStatusIndicator
              label={statusIndicator.label}
              tone={statusIndicator.tone}
            />
          ) : null}
          {testAction}
          <DirtySaveButton
            dirty={dirty}
            saving={saving}
            disabled={saveDisabled}
            onClick={onSave}
          />
        </>
      )}
    >
      {children}
    </AdminSurface>
  );
}

function ConfigCardStatusIndicator({
  label,
  tone,
}: {
  label: ReactNode;
  tone: ConfigStatusTone;
}) {
  const toneClassName =
    tone === "pending"
      ? {
          shell:
            "border-slate-400/20 bg-slate-500/8 text-slate-600 dark:text-slate-300",
          dot: "bg-slate-400 shadow-[0_0_0_4px_rgba(148,163,184,0.12),0_0_14px_rgba(148,163,184,0.28)]",
        }
      : tone === "available"
      ? {
          shell:
            "border-emerald-500/20 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
          dot: "bg-emerald-500 shadow-[0_0_0_4px_rgba(34,197,94,0.16),0_0_18px_rgba(34,197,94,0.6)]",
        }
      : tone === "checking"
        ? {
            shell:
              "border-amber-500/20 bg-amber-500/10 text-amber-700 dark:text-amber-300",
            dot: "bg-amber-500 animate-pulse shadow-[0_0_0_4px_rgba(245,158,11,0.14),0_0_16px_rgba(245,158,11,0.45)]",
          }
        : {
            shell:
              "border-rose-500/20 bg-rose-500/10 text-rose-700 dark:text-rose-300",
            dot: "bg-rose-500 shadow-[0_0_0_4px_rgba(244,63,94,0.14),0_0_16px_rgba(244,63,94,0.45)]",
          };

  return (
    <div
      className={cn(
        "inline-flex h-9 items-center gap-2 rounded-full border px-3 text-xs font-medium",
        toneClassName.shell,
      )}
    >
      <span className={cn("h-2.5 w-2.5 rounded-full", toneClassName.dot)} />
      <span>{label}</span>
    </div>
  );
}
