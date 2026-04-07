import { useEffect, useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  getListPageCopyQueryKey,
  useListPageCopy,
  useUpdatePageCopy,
} from "@serino/api-client/admin";
import { toast } from "sonner";
import { MarkdownEditor } from "@/components/MarkdownEditor";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { DirtySaveButton, PendingSaveBadge } from "@/components/ui/DirtySaveButton";
import { Label } from "@/components/ui/Label";
import { useI18n } from "@/i18n";
import { extractApiErrorMessage } from "@/lib/api-error";
import { FRIENDS_PAGE_KEY } from "./friendConfig";

export function FriendsPageContentSection() {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const { data: pageCopyRaw, isLoading } = useListPageCopy();
  const pageCopy = useMemo(
    () => pageCopyRaw?.data?.items?.find((item) => item.page_key === FRIENDS_PAGE_KEY) ?? null,
    [pageCopyRaw],
  );
  const savedMarkdown = useMemo(
    () =>
      typeof pageCopy?.extras?.applicationMarkdown === "string"
        ? pageCopy.extras.applicationMarkdown
        : "",
    [pageCopy],
  );
  const [markdown, setMarkdown] = useState("");

  useEffect(() => {
    if (!pageCopy) {
      return;
    }
    setMarkdown(savedMarkdown);
  }, [pageCopy, savedMarkdown]);

  const saveContent = useUpdatePageCopy({
    mutation: {
      onSuccess: () => {
        void queryClient.invalidateQueries({ queryKey: getListPageCopyQueryKey() });
        toast.success(t("common.operationSuccess"));
      },
      onError: (error: any) => {
        toast.error(extractApiErrorMessage(error, t("common.operationFailed")));
      },
    },
  });

  const hasChanges = markdown !== savedMarkdown;

  if (isLoading) {
    return (
      <Card>
        <CardContent className="py-10 text-sm text-muted-foreground">{t("common.loading")}</CardContent>
      </Card>
    );
  }

  if (!pageCopy) {
    return (
      <Card>
        <CardContent className="py-10 text-sm text-muted-foreground">
          {t("friends.moreConfigMissing")}
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader className="gap-4 pb-5 sm:flex-row sm:items-start sm:justify-between sm:space-y-0">
        <div className="space-y-1">
          <CardTitle className="text-lg">{t("friends.pageContentTitle")}</CardTitle>
          <p className="text-sm text-muted-foreground">{t("friends.pageContentDescription")}</p>
        </div>
        <div className="flex items-center gap-2 self-start">
          {hasChanges ? <PendingSaveBadge /> : null}
          <DirtySaveButton
            dirty={hasChanges}
            saving={saveContent.isPending}
            onClick={() =>
              saveContent.mutate({
                itemId: pageCopy.id,
                data: {
                  extras: {
                    ...pageCopy.extras,
                    applicationMarkdown: markdown,
                  },
                },
              })
            }
          />
        </div>
      </CardHeader>

      <CardContent className="space-y-3">
        <div className="space-y-2">
          <Label>{t("friends.pageContentLabel")}</Label>
          <MarkdownEditor
            value={markdown}
            onChange={setMarkdown}
            placeholder={t("friends.pageContentPlaceholder")}
            minHeight="360px"
          />
        </div>
      </CardContent>
    </Card>
  );
}
