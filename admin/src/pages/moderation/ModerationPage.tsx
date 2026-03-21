import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { listComments, moderateComment, listGuestbook, moderateGuestbook } from "@/api/endpoints/comments";
import { PageHeader } from "@/components/PageHeader";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/Tabs";
import { DataTable } from "@/components/DataTable";
import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Label } from "@/components/ui/Label";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/Dialog";
import { formatDate } from "@/lib/utils";
import { Check, X, Trash2, History } from "lucide-react";
import { useI18n } from "@/i18n";
import type { Comment, GuestbookEntry } from "@/types/models";

export default function ModerationPage() {
  const { t } = useI18n();
  return (
    <div>
      <PageHeader title={t("moderation.title")} description={t("moderation.description")} />
      <Tabs defaultValue="comments">
        <TabsList>
          <TabsTrigger value="comments">{t("moderation.comments")}</TabsTrigger>
          <TabsTrigger value="guestbook">{t("moderation.guestbook")}</TabsTrigger>
        </TabsList>
        <TabsContent value="comments"><CommentsTab /></TabsContent>
        <TabsContent value="guestbook"><GuestbookTab /></TabsContent>
      </Tabs>
    </div>
  );
}

function useReasonDialog() {
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [pending, setPending] = useState<{ id: string; action: "approve" | "reject" | "delete" } | null>(null);

  function prompt(id: string, action: "approve" | "reject" | "delete") {
    setPending({ id, action });
    setReason("");
    setOpen(true);
  }

  function close() {
    setOpen(false);
    setPending(null);
    setReason("");
  }

  return { open, reason, setReason, pending, prompt, close };
}

function ReasonDialog({ dialog, onConfirm, isPending }: {
  dialog: ReturnType<typeof useReasonDialog>;
  onConfirm: (id: string, action: "approve" | "reject" | "delete", reason: string) => void;
  isPending: boolean;
}) {
  const { t } = useI18n();
  return (
    <Dialog open={dialog.open} onOpenChange={(v) => { if (!v) dialog.close(); }}>
      <DialogContent className="max-w-sm">
        <DialogHeader><DialogTitle className="capitalize">{dialog.pending?.action} Item</DialogTitle></DialogHeader>
        <div className="space-y-3">
          <div className="space-y-1">
            <Label>{t("moderation.reason")}</Label>
            <Input value={dialog.reason} onChange={(e) => dialog.setReason(e.target.value)} placeholder={t("moderation.enterReason")} />
          </div>
          <div className="flex gap-2 justify-end">
            <Button variant="outline" onClick={() => dialog.close()}>{t("common.cancel")}</Button>
            <Button
              variant={dialog.pending?.action === "delete" ? "destructive" : "default"}
              onClick={() => { if (dialog.pending) onConfirm(dialog.pending.id, dialog.pending.action, dialog.reason); }}
              disabled={isPending}
            >
              {t("common.confirm")}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function ModerationHistory({ item }: { item: Comment | GuestbookEntry }) {
  const { t } = useI18n();
  return (
    <div className="text-xs text-muted-foreground space-y-1">
      <div className="flex items-center gap-1"><History className="h-3 w-3" /> {t("moderation.currentStatus")} <StatusBadge status={item.status} /></div>
      <div>{t("moderation.created")} {formatDate(item.created_at)}</div>
      <div>{t("moderation.updated")} {formatDate(item.updated_at)}</div>
    </div>
  );
}

function CommentsTab() {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState("");
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const dialog = useReasonDialog();
  const { data, isLoading } = useQuery({
    queryKey: ["comments", page, statusFilter],
    queryFn: () => listComments({ page, status: statusFilter || undefined }),
  });

  const moderate = useMutation({
    mutationFn: ({ id, action, reason }: { id: string; action: "approve" | "reject" | "delete"; reason?: string }) =>
      moderateComment(id, { action, reason: reason || null }),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["comments"] }); dialog.close(); },
  });

  return (
    <div className="mt-4">
      <ReasonDialog dialog={dialog} onConfirm={(id, action, reason) => moderate.mutate({ id, action, reason })} isPending={moderate.isPending} />
      <Tabs value={statusFilter} onValueChange={(v) => { setStatusFilter(v); setPage(1); }}>
        <TabsList className="mb-4">
          <TabsTrigger value="">{t("common.all")}</TabsTrigger>
          <TabsTrigger value="pending">{t("moderation.pending")}</TabsTrigger>
          <TabsTrigger value="approved">{t("moderation.approved")}</TabsTrigger>
          <TabsTrigger value="rejected">{t("moderation.rejected")}</TabsTrigger>
        </TabsList>
      </Tabs>
      <div className="border rounded-lg">
        <DataTable<Comment>
          columns={[
            { header: t("common.author"), accessor: "author_name" },
            { header: t("common.body"), accessor: (row) => <span className="line-clamp-2 max-w-md">{row.body}</span> },
            { header: t("common.type"), accessor: "content_type" },
            { header: t("common.status"), accessor: (row) => <StatusBadge status={row.status} /> },
            { header: t("common.date"), accessor: (row) => formatDate(row.created_at) },
            {
              header: t("common.actions"),
              accessor: (row) => (
                <div className="flex gap-1">
                  <Button variant="ghost" size="icon" onClick={(e) => { e.stopPropagation(); dialog.prompt(row.id, "approve"); }} title={t("moderation.approve")}><Check className="h-4 w-4 text-green-600" /></Button>
                  <Button variant="ghost" size="icon" onClick={(e) => { e.stopPropagation(); dialog.prompt(row.id, "reject"); }} title={t("moderation.reject")}><X className="h-4 w-4 text-orange-600" /></Button>
                  <Button variant="ghost" size="icon" onClick={(e) => { e.stopPropagation(); dialog.prompt(row.id, "delete"); }} title={t("common.delete")}><Trash2 className="h-4 w-4 text-red-600" /></Button>
                  <Button variant="ghost" size="icon" onClick={(e) => { e.stopPropagation(); setExpandedId(expandedId === row.id ? null : row.id); }} title={t("moderation.history")}><History className="h-4 w-4" /></Button>
                </div>
              ),
            },
          ]}
          data={data?.items ?? []}
          total={data?.total ?? 0}
          page={page}
          pageSize={data?.page_size ?? 20}
          onPageChange={setPage}
          isLoading={isLoading}
        />
      </div>
      {expandedId && data?.items && (() => {
        const item = data.items.find((c) => c.id === expandedId);
        return item ? (
          <div className="mt-2 p-3 border rounded-lg bg-muted/50">
            <ModerationHistory item={item} />
          </div>
        ) : null;
      })()}
    </div>
  );
}

function GuestbookTab() {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState("");
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const dialog = useReasonDialog();
  const { data, isLoading } = useQuery({
    queryKey: ["guestbook", page, statusFilter],
    queryFn: () => listGuestbook({ page, status: statusFilter || undefined }),
  });

  const moderate = useMutation({
    mutationFn: ({ id, action, reason }: { id: string; action: "approve" | "reject" | "delete"; reason?: string }) =>
      moderateGuestbook(id, { action, reason: reason || null }),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["guestbook"] }); dialog.close(); },
  });

  return (
    <div className="mt-4">
      <ReasonDialog dialog={dialog} onConfirm={(id, action, reason) => moderate.mutate({ id, action, reason })} isPending={moderate.isPending} />
      <Tabs value={statusFilter} onValueChange={(v) => { setStatusFilter(v); setPage(1); }}>
        <TabsList className="mb-4">
          <TabsTrigger value="">{t("common.all")}</TabsTrigger>
          <TabsTrigger value="pending">{t("moderation.pending")}</TabsTrigger>
          <TabsTrigger value="approved">{t("moderation.approved")}</TabsTrigger>
          <TabsTrigger value="rejected">{t("moderation.rejected")}</TabsTrigger>
        </TabsList>
      </Tabs>
      <div className="border rounded-lg">
        <DataTable<GuestbookEntry>
          columns={[
            { header: t("common.name"), accessor: "name" },
            { header: t("common.body"), accessor: (row) => <span className="line-clamp-2 max-w-md">{row.body}</span> },
            { header: t("common.website"), accessor: (row) => row.website || "-" },
            { header: t("common.status"), accessor: (row) => <StatusBadge status={row.status} /> },
            { header: t("common.date"), accessor: (row) => formatDate(row.created_at) },
            {
              header: t("common.actions"),
              accessor: (row) => (
                <div className="flex gap-1">
                  <Button variant="ghost" size="icon" onClick={(e) => { e.stopPropagation(); dialog.prompt(row.id, "approve"); }}><Check className="h-4 w-4 text-green-600" /></Button>
                  <Button variant="ghost" size="icon" onClick={(e) => { e.stopPropagation(); dialog.prompt(row.id, "reject"); }}><X className="h-4 w-4 text-orange-600" /></Button>
                  <Button variant="ghost" size="icon" onClick={(e) => { e.stopPropagation(); dialog.prompt(row.id, "delete"); }}><Trash2 className="h-4 w-4 text-red-600" /></Button>
                  <Button variant="ghost" size="icon" onClick={(e) => { e.stopPropagation(); setExpandedId(expandedId === row.id ? null : row.id); }}><History className="h-4 w-4" /></Button>
                </div>
              ),
            },
          ]}
          data={data?.items ?? []}
          total={data?.total ?? 0}
          page={page}
          pageSize={data?.page_size ?? 20}
          onPageChange={setPage}
          isLoading={isLoading}
        />
      </div>
      {expandedId && data?.items && (() => {
        const item = data.items.find((c) => c.id === expandedId);
        return item ? (
          <div className="mt-2 p-3 border rounded-lg bg-muted/50">
            <ModerationHistory item={item} />
          </div>
        ) : null;
      })()}
    </div>
  );
}
