import { Braces, ChevronRight, Copy, KeyRound, Terminal } from "lucide-react";
import {
  forwardRef,
  type ComponentPropsWithoutRef,
  type ComponentType,
  type ReactNode,
} from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/Button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/Dialog";
import { useI18n } from "@/i18n";
import { cn } from "@/lib/utils";

interface McpInstallGuideProps {
  endpoint: string;
  usageUrl: string;
}

interface InstallCommands {
  codex: string;
  claude: string;
  updateKey: string;
}

export function buildMcpInstallCommands(endpoint: string): InstallCommands {
  const fallbackOrigin = typeof window === "undefined" ? "http://localhost" : window.location.origin;
  let origin = fallbackOrigin;

  try {
    origin = new URL(endpoint, fallbackOrigin).origin;
  } catch {
    // Keep the current site as the safe fallback for a malformed configuration value.
  }

  return {
    codex: `curl -fsSL ${origin}/mcp/install/codex.sh | sh`,
    claude: `curl -fsSL ${origin}/mcp/install/claude.sh | sh`,
    updateKey: "~/.local/bin/serino-mcp-key",
  };
}

function CommandCard({
  client,
  command,
  copyLabel,
  onCopy,
}: {
  client: string;
  command: string;
  copyLabel: string;
  onCopy: () => void;
}) {
  return (
    <div className="rounded-[var(--admin-radius-md)] border border-border/55 bg-background/50 p-3">
      <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-foreground/90">
        <Terminal className="h-4 w-4 text-[rgb(var(--admin-accent-rgb)/0.8)]" />
        <span>{client}</span>
      </div>
      <CopyableCommand
        command={command}
        copyLabel={copyLabel}
        onCopy={onCopy}
      />
    </div>
  );
}

function CopyableCommand({
  command,
  copyLabel,
  onCopy,
}: {
  command: string;
  copyLabel: string;
  onCopy: () => void;
}) {
  return (
    <div className="relative">
      <code className="block min-h-10 whitespace-pre-wrap break-all rounded-md bg-muted/60 py-2 pl-3 pr-11 text-xs leading-5 text-foreground/85">
        {command}
      </code>
      <Button
        type="button"
        variant="ghost"
        size="icon"
        className="absolute right-1 top-1 min-h-8 h-8 w-8"
        aria-label={copyLabel}
        title={copyLabel}
        onClick={onCopy}
      >
        <Copy className="h-3.5 w-3.5" />
      </Button>
    </div>
  );
}

function StepNumber({ number }: { number: number }) {
  return (
    <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-[rgb(var(--admin-accent-rgb)/0.11)] text-xs font-semibold text-[rgb(var(--admin-accent-rgb)/0.9)]">
      {number}
    </span>
  );
}

function SetupStep({
  number,
  title,
  description,
}: {
  number: number;
  title: string;
  description?: ReactNode;
}) {
  return (
    <div className="flex gap-3">
      <StepNumber number={number} />
      <div className="min-w-0">
        <div className="text-sm font-semibold text-foreground/90">{title}</div>
        {description ? (
          <div className="mt-1 text-sm leading-6 text-muted-foreground">{description}</div>
        ) : null}
      </div>
    </div>
  );
}

interface GuideTriggerProps extends Omit<ComponentPropsWithoutRef<"button">, "title"> {
  icon: ComponentType<{ className?: string }>;
  title: string;
}

const GuideTrigger = forwardRef<HTMLButtonElement, GuideTriggerProps>(
  ({ icon: Icon, title, className, ...props }, ref) => (
    <button
      ref={ref}
      type="button"
      className={cn(
        "group flex w-full items-center gap-3 px-3 py-3 text-left admin-transition-fast hover:bg-white/35 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring dark:hover:bg-white/[0.05]",
        className,
      )}
      {...props}
    >
      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-[var(--admin-radius-md)] bg-[rgb(var(--admin-accent-rgb)/0.09)] text-[rgb(var(--admin-accent-rgb)/0.82)]">
        <Icon className="h-4 w-4" />
      </span>
      <span className="min-w-0 flex-1 text-sm font-medium text-foreground/90">{title}</span>
      <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground/55 admin-transition-fast group-hover:translate-x-0.5 group-hover:text-foreground/70" />
    </button>
  ),
);
GuideTrigger.displayName = "GuideTrigger";

export function McpInstallGuide({ endpoint, usageUrl }: McpInstallGuideProps) {
  const { t } = useI18n();
  const commands = buildMcpInstallCommands(endpoint);

  const copyCommand = async (client: string, command: string) => {
    try {
      await navigator.clipboard.writeText(command);
      toast.success(t("integrations.mcpInstallCommandCopied", { client }));
    } catch {
      toast.error(t("integrations.mcpInstallCopyFailed"));
    }
  };

  return (
    <div>
      <div className="text-xs font-medium uppercase tracking-[0.16em] text-muted-foreground">
        {t("integrations.mcpUsageGuides")}
      </div>

      <div className="mt-3 divide-y divide-border/55 overflow-hidden rounded-[var(--admin-radius-lg)] border border-border/55 bg-muted/20">
        <Dialog>
          <DialogTrigger asChild>
            <GuideTrigger
              icon={Braces}
              title={t("integrations.mcpRestGuideTitle")}
            />
          </DialogTrigger>
          <DialogContent className="max-h-[min(88vh,720px)] max-w-xl gap-4 overflow-y-auto rounded-[var(--admin-radius-xl)]">
            <DialogHeader className="pr-7 text-left">
              <DialogTitle>{t("integrations.mcpRestGuideTitle")}</DialogTitle>
              <DialogDescription className="sr-only">
                {t("integrations.mcpRestDialogDescription")}
              </DialogDescription>
            </DialogHeader>

            <ol className="grid gap-3">
              <li className="rounded-[var(--admin-radius-md)] border border-border/45 bg-muted/25 p-4">
                <SetupStep
                  number={1}
                  title={t("integrations.mcpRestStepCreateKeyTitle")}
                  description={t("integrations.mcpRestStepCreateKeyDescription")}
                />
              </li>
              <li className="rounded-[var(--admin-radius-md)] border border-border/45 bg-muted/25 p-4">
                <SetupStep
                  number={2}
                  title={t("integrations.mcpRestStepAgentTitle")}
                  description={
                    <>
                      {t("integrations.mcpRestStepAgentPrefix")} {" "}
                      <a
                        className="break-all font-medium text-[rgb(var(--admin-accent-rgb)/0.92)] underline decoration-[rgb(var(--admin-accent-rgb)/0.35)] underline-offset-2 hover:decoration-current"
                        href={usageUrl}
                        target="_blank"
                        rel="noreferrer"
                      >
                        {usageUrl}
                      </a>{" "}
                      {t("integrations.mcpRestStepAgentSuffix")}
                    </>
                  }
                />
              </li>
              <li className="rounded-[var(--admin-radius-md)] border border-border/45 bg-muted/25 p-4">
                <SetupStep
                  number={3}
                  title={t("integrations.mcpRestStepReadyTitle")}
                  description={t("integrations.mcpRestStepReadyDescription")}
                />
              </li>
            </ol>
          </DialogContent>
        </Dialog>

        <Dialog>
          <DialogTrigger asChild>
            <GuideTrigger
              icon={Terminal}
              title={t("integrations.mcpClientGuideTitle")}
            />
          </DialogTrigger>
          <DialogContent className="max-h-[min(90vh,780px)] max-w-2xl gap-5 overflow-y-auto rounded-[var(--admin-radius-xl)]">
            <DialogHeader className="pr-7 text-left">
              <DialogTitle>{t("integrations.mcpClientGuideTitle")}</DialogTitle>
              <DialogDescription className="sr-only">
                {t("integrations.mcpClientDialogDescription")}
              </DialogDescription>
            </DialogHeader>

            <ol className="grid gap-3">
              <li className="grid gap-3">
                <SetupStep
                  number={1}
                  title={t("integrations.mcpClientStepInstall")}
                />
                <div className="grid gap-3 sm:grid-cols-2">
                  <CommandCard
                    client="Codex"
                    command={commands.codex}
                    copyLabel={t("integrations.mcpInstallCopyCommand", { client: "Codex" })}
                    onCopy={() => void copyCommand("Codex", commands.codex)}
                  />
                  <CommandCard
                    client="Claude Code"
                    command={commands.claude}
                    copyLabel={t("integrations.mcpInstallCopyCommand", { client: "Claude Code" })}
                    onCopy={() => void copyCommand("Claude Code", commands.claude)}
                  />
                </div>
              </li>
              <li className="rounded-[var(--admin-radius-md)] bg-muted/35 p-3">
                <SetupStep
                  number={2}
                  title={t("integrations.mcpClientStepCredential")}
                />
              </li>
              <li className="rounded-[var(--admin-radius-md)] bg-muted/35 p-3">
                <SetupStep
                  number={3}
                  title={t("integrations.mcpClientStepReload")}
                />
              </li>
            </ol>

            <div className="border-t border-border/55 pt-4">
              <div className="mb-3 flex items-start gap-2.5">
                <KeyRound className="mt-0.5 h-4 w-4 shrink-0 text-[rgb(var(--admin-accent-rgb)/0.82)]" />
                <div>
                  <div className="text-sm font-semibold text-foreground/90">
                    {t("integrations.mcpUpdateKey")}
                  </div>
                  <p className="mt-1 text-sm leading-6 text-muted-foreground">
                    {t("integrations.mcpUpdateKeyDescription")}
                  </p>
                </div>
              </div>
              <CopyableCommand
                command={commands.updateKey}
                copyLabel={t("integrations.mcpCopyKeyCommand")}
                onCopy={() =>
                  void copyCommand(t("integrations.mcpUpdateKey"), commands.updateKey)
                }
              />
            </div>
          </DialogContent>
        </Dialog>
      </div>
    </div>
  );
}
