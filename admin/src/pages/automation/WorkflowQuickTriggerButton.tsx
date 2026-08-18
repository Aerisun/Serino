import { useCallback, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  getGetMessagesApiV1AdminAutomationMessagesGetQueryKey,
  getGetOverviewApiV1AdminAutomationOverviewGetQueryKey,
  getGetRunsApiV1AdminAutomationRunsGetQueryKey,
} from "@serino/api-client/admin";
import { useNavigate } from "react-router-dom";
import { Loader2, MessageSquareText, Play } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/Button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/Dialog";
import { Label } from "@/components/ui/Label";
import { Textarea } from "@/components/ui/Textarea";
import { useI18n } from "@/i18n";
import type { AgentWorkflow } from "@/pages/automation/api";
import {
  createAgentWorkflowMessageRun,
  createAgentWorkflowRun,
} from "@/pages/automation/api";

interface WorkflowQuickTriggerButtonProps {
  workflow: AgentWorkflow;
}

type QuickTriggerType = "trigger.manual" | "trigger.message";

function resolveQuickTriggerType(workflow: AgentWorkflow): QuickTriggerType | null {
  const enabledBindings = workflow.trigger_bindings.filter((binding) => binding.enabled);
  if (enabledBindings.length !== 1) return null;
  const triggerType = enabledBindings[0]?.type;
  return triggerType === "trigger.manual" || triggerType === "trigger.message"
    ? triggerType
    : null;
}

export function WorkflowQuickTriggerButton({
  workflow,
}: WorkflowQuickTriggerButtonProps) {
  const { lang } = useI18n();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [messageDialogOpen, setMessageDialogOpen] = useState(false);
  const [messageDraft, setMessageDraft] = useState("");
  const [isTriggering, setIsTriggering] = useState(false);
  const triggerType = resolveQuickTriggerType(workflow);

  const refreshActivityQueries = useCallback(async () => {
    await Promise.all([
      queryClient.invalidateQueries({
        queryKey: getGetRunsApiV1AdminAutomationRunsGetQueryKey(),
      }),
      queryClient.invalidateQueries({
        queryKey: getGetMessagesApiV1AdminAutomationMessagesGetQueryKey(),
      }),
      queryClient.invalidateQueries({
        queryKey: getGetOverviewApiV1AdminAutomationOverviewGetQueryKey(),
      }),
    ]);
  }, [queryClient]);

  const runWorkflow = useCallback(
    async (message?: string) => {
      if (!triggerType || !workflow.enabled || isTriggering) return;
      const normalizedMessage = message?.trim() ?? "";
      if (triggerType === "trigger.message" && !normalizedMessage) {
        toast.error(
          lang === "zh"
            ? "请输入要交给工作流的留言。"
            : "Enter a message for the workflow.",
        );
        return;
      }

      setIsTriggering(true);
      try {
        const result =
          triggerType === "trigger.message"
            ? await createAgentWorkflowMessageRun(workflow.key, {
                message: normalizedMessage,
                execute_immediately: true,
              })
            : await createAgentWorkflowRun(workflow.key, {
                execute_immediately: true,
              });
        await refreshActivityQueries();
        setMessageDialogOpen(false);
        setMessageDraft("");
        navigate(`/agent/activity/runs/${result.run.id}`);
        toast.success(lang === "zh" ? "工作流已触发。" : "Workflow triggered.");
      } catch (error) {
        toast.error(
          error instanceof Error
            ? error.message
            : lang === "zh"
              ? "工作流触发失败。"
              : "Failed to trigger workflow.",
        );
      } finally {
        setIsTriggering(false);
      }
    },
    [
      isTriggering,
      lang,
      navigate,
      refreshActivityQueries,
      triggerType,
      workflow.enabled,
      workflow.key,
    ],
  );

  if (!triggerType) return null;

  const isMessageTrigger = triggerType === "trigger.message";
  const disabled = !workflow.enabled || isTriggering;
  const disabledTitle = !workflow.enabled
    ? lang === "zh"
      ? "请先启用工作流"
      : "Enable the workflow first"
    : undefined;

  return (
    <>
      <Button
        type="button"
        variant="outline"
        size="sm"
        onClick={() => {
          if (isMessageTrigger) {
            setMessageDialogOpen(true);
            return;
          }
          void runWorkflow();
        }}
        disabled={disabled}
        title={disabledTitle}
      >
        {isTriggering ? (
          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
        ) : isMessageTrigger ? (
          <MessageSquareText className="mr-2 h-4 w-4" />
        ) : (
          <Play className="mr-2 h-4 w-4" />
        )}
        {isMessageTrigger
          ? lang === "zh"
            ? "留言触发"
            : "Message trigger"
          : lang === "zh"
            ? "手动触发"
            : "Run manually"}
      </Button>

      {isMessageTrigger ? (
        <Dialog
          open={messageDialogOpen}
          onOpenChange={(nextOpen) => {
            if (!isTriggering) setMessageDialogOpen(nextOpen);
          }}
        >
          <DialogContent className="max-w-xl">
            <DialogHeader className="pr-7 text-left">
              <DialogTitle>
                {lang === "zh" ? "留言触发" : "Trigger with message"}
              </DialogTitle>
              <DialogDescription>
                {lang === "zh"
                  ? "输入内容网址和你的关注重点。它们会作为一份完整留言进入工作流。"
                  : "Enter the content URL and your review focus. The complete message will enter the workflow."}
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-2">
              <Label htmlFor={`workflow-trigger-message-${workflow.key}`}>
                {lang === "zh" ? "留言内容" : "Message"}
              </Label>
              <Textarea
                id={`workflow-trigger-message-${workflow.key}`}
                value={messageDraft}
                onChange={(event) => setMessageDraft(event.target.value)}
                placeholder={
                  lang === "zh"
                    ? "例如：https://example.com/my-story\n请重点欣赏叙事节奏、意象和结尾，并给出具体建议。"
                    : "Example: https://example.com/my-story\nFocus on pacing, imagery, and the ending, then give specific suggestions."
                }
                className="min-h-40 resize-y"
                maxLength={20_000}
                autoFocus
              />
              <div className="text-right text-xs text-muted-foreground">
                {messageDraft.length.toLocaleString()} / 20,000
              </div>
            </div>
            <div className="flex justify-end gap-2">
              <Button
                type="button"
                variant="ghost"
                onClick={() => setMessageDialogOpen(false)}
                disabled={isTriggering}
              >
                {lang === "zh" ? "取消" : "Cancel"}
              </Button>
              <Button
                type="button"
                onClick={() => void runWorkflow(messageDraft)}
                disabled={!messageDraft.trim() || isTriggering}
              >
                {isTriggering ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <MessageSquareText className="mr-2 h-4 w-4" />
                )}
                {lang === "zh" ? "开始工作流" : "Start workflow"}
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      ) : null}
    </>
  );
}
