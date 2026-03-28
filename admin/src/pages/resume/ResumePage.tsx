import { useEffect, useMemo, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { PREVIEW_DATA_MESSAGE, isPreviewRequestMessage } from "@serino/utils";
import {
  getListBasicsQueryKey,
  useCreateBasics,
  useListBasics,
  useSystemInfoApiV1AdminSystemInfoGet,
  useUpdateBasics,
} from "@serino/api-client/admin";
import type { ResumeBasicsCreate } from "@serino/api-client/models";
import { ExternalLink, Save } from "lucide-react";
import { MarkdownEditor } from "@/components/MarkdownEditor";
import { PageHeader } from "@/components/PageHeader";
import { ResourceUploadField } from "@/components/ResourceUploadField";
import { Button } from "@/components/ui/Button";
import { Card, CardContent } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { Label } from "@/components/ui/Label";
import { toast } from "sonner";

type BasicsForm = {
  title: string;
  summary: string;
  location: string;
  email: string;
  profile_image_url: string;
};

type ResumePreviewPayload = BasicsForm & { type: "resume" };

const EMPTY_FORM: BasicsForm = {
  title: "",
  summary: "",
  location: "",
  email: "",
  profile_image_url: "",
};

function toApiPayload(form: BasicsForm): ResumeBasicsCreate {
  return {
    title: form.title,
    subtitle: "",
    summary: form.summary,
    download_label: "",
    template_key: "editorial",
    accent_tone: "amber",
    location: form.location,
    availability: "",
    email: form.email,
    website: "",
    profile_image_url: form.profile_image_url,
    highlights: [],
  };
}

function mutationError(error: unknown) {
  const detail = (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
  return detail || "操作失败";
}

export default function ResumePage() {
  const queryClient = useQueryClient();
  const basicsQuery = useListBasics();
  const existing = basicsQuery.data?.data?.items?.[0];
  const [form, setForm] = useState<BasicsForm>(EMPTY_FORM);

  useEffect(() => {
    if (!existing) return;
    setForm({
      title: existing.title ?? "",
      summary: existing.summary ?? "",
      location: existing.location ?? "",
      email: existing.email ?? "",
      profile_image_url: existing.profile_image_url ?? "",
    });
  }, [existing]);

  const createBasics = useCreateBasics({
    mutation: {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: getListBasicsQueryKey() });
        toast.success("简历配置已保存");
      },
      onError: (error) => toast.error(mutationError(error)),
    },
  });

  const updateBasics = useUpdateBasics({
    mutation: {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: getListBasicsQueryKey() });
        toast.success("简历配置已更新");
      },
      onError: (error) => toast.error(mutationError(error)),
    },
  });

  const saving = createBasics.isPending || updateBasics.isPending;

  function handleSave() {
    const payload = toApiPayload(form);
    if (existing) {
      updateBasics.mutate({ itemId: existing.id, data: payload });
      return;
    }
    createBasics.mutate({ data: payload });
  }

  const [previewOpen, setPreviewOpen] = useState(false);
  const previewWindowRef = useRef<Window | null>(null);
  const { data: systemInfo } = useSystemInfoApiV1AdminSystemInfoGet();
  const frontendUrl = (systemInfo?.site_url || "http://localhost:8080").replace(/\/+$/, "");
  const frontendOrigin = new URL(frontendUrl, window.location.origin).origin;
  const storageKey = "aerisun-preview-resume";
  const previewPayload = useMemo<ResumePreviewPayload>(() => ({ type: "resume", ...form }), [form]);

  useEffect(() => {
    if (!previewOpen) return;

    const previewWindow = previewWindowRef.current;
    if (!previewWindow || previewWindow.closed) {
      setPreviewOpen(false);
      return;
    }

    localStorage.setItem(storageKey, JSON.stringify(previewPayload));
    previewWindow.postMessage({ type: PREVIEW_DATA_MESSAGE, storageKey, payload: previewPayload }, frontendOrigin);
  }, [frontendOrigin, previewOpen, previewPayload]);

  useEffect(() => {
    const onMessage = (event: MessageEvent) => {
      if (event.origin !== frontendOrigin) return;
      if (!isPreviewRequestMessage(event.data)) return;
      if (event.data.storageKey !== storageKey) return;
      if (!event.source) return;

      localStorage.setItem(storageKey, JSON.stringify(previewPayload));
      (event.source as WindowProxy).postMessage(
        { type: PREVIEW_DATA_MESSAGE, storageKey, payload: previewPayload },
        event.origin
      );
    };

    window.addEventListener("message", onMessage);
    return () => window.removeEventListener("message", onMessage);
  }, [frontendOrigin, previewPayload]);

  const openPreview = () => {
    const existingWindow = previewWindowRef.current;
    if (existingWindow && !existingWindow.closed) {
      localStorage.setItem(storageKey, JSON.stringify(previewPayload));
      existingWindow.postMessage({ type: PREVIEW_DATA_MESSAGE, storageKey, payload: previewPayload }, frontendOrigin);
      existingWindow.focus();
      setPreviewOpen(true);
      return;
    }

    localStorage.setItem(storageKey, JSON.stringify(previewPayload));
    const previewWindow = window.open(`${frontendUrl}/preview?storageKey=${encodeURIComponent(storageKey)}`, "_blank");
    previewWindowRef.current = previewWindow;
    setPreviewOpen(Boolean(previewWindow));

    if (previewWindow) {
      window.setTimeout(() => {
        if (previewWindow.closed) {
          setPreviewOpen(false);
          return;
        }

        previewWindow.postMessage({ type: PREVIEW_DATA_MESSAGE, storageKey, payload: previewPayload }, frontendOrigin);
      }, 250);
    }
  };

  return (
    <div>
      <PageHeader
        title="Markdown 简历"
        description="去掉 PDF 下载，收成一套固定版式。后台只保留必要信息和 Markdown 正文。"
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <Button variant="outline" className="preview-glow-button" onClick={openPreview}>
              <ExternalLink className="mr-2 h-4 w-4" />
              真实页面预览
            </Button>
            <Button
              variant="secondary"
              className="bg-slate-100 text-slate-900 border-slate-200 shadow-none backdrop-blur-0 ring-0 hover:bg-slate-200 hover:text-slate-950 dark:bg-slate-800/80 dark:text-slate-100 dark:border-slate-700 dark:hover:bg-slate-800"
              onClick={handleSave}
              disabled={saving}
            >
              <Save className="mr-2 h-4 w-4" />
              {saving ? "保存中…" : "保存简历"}
            </Button>
          </div>
        }
      />

      <div className="mt-5 space-y-6">
        <Card className="rounded-[1.8rem] border border-white/60 bg-[rgba(255,255,255,0.72)] shadow-[0_24px_70px_rgba(15,23,42,0.07)]">
          <CardContent className="p-6">
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label>姓名 / 页面标题</Label>
                <Input value={form.title} onChange={(e) => setForm((p) => ({ ...p, title: e.target.value }))} />
              </div>
              <div className="space-y-2">
                <Label>所在地</Label>
                <Input value={form.location} onChange={(e) => setForm((p) => ({ ...p, location: e.target.value }))} />
              </div>
              <div className="space-y-2">
                <Label>邮箱</Label>
                <Input value={form.email} onChange={(e) => setForm((p) => ({ ...p, email: e.target.value }))} />
              </div>
              <div className="space-y-2">
                <ResourceUploadField
                  label="头像地址"
                  value={form.profile_image_url}
                  category="resume-avatar"
                  accept="image/*"
                  placeholder="上传或填写头像地址"
                  note="简历默认头像"
                  uniqueByCategory
                  onChange={(value) => setForm((p) => ({ ...p, profile_image_url: value }))}
                />
              </div>
            </div>

            <div className="mt-5 space-y-2">
              <Label>Markdown 简历正文</Label>
              <MarkdownEditor
                value={form.summary}
                onChange={(value) => setForm((p) => ({ ...p, summary: value }))}
                minHeight="460px"
                placeholder="使用 Markdown 编写简历正文"
              />
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
