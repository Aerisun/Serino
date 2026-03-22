import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  listResumeBasics, createResumeBasics, updateResumeBasics,
  listResumeSkills, createResumeSkill, deleteResumeSkill,
  listResumeExperiences, createResumeExperience, deleteResumeExperience,
} from "@/api/endpoints/resume";
import { PageHeader } from "@/components/PageHeader";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/Tabs";
import { DataTable } from "@/components/DataTable";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Textarea } from "@/components/ui/Textarea";
import { Label } from "@/components/ui/Label";
import { Card, CardContent } from "@/components/ui/Card";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/Dialog";
import { Plus, Save, Trash2 } from "lucide-react";
import { useI18n } from "@/i18n";
import type { ResumeSkillGroup, ResumeExperience } from "@/types/models";

export default function ResumePage() {
  const { t } = useI18n();
  return (
    <div>
      <PageHeader title={t("resume.title")} description={t("resume.description")} />
      <Tabs defaultValue="basics">
        <TabsList>
          <TabsTrigger value="basics">{t("resume.basics")}</TabsTrigger>
          <TabsTrigger value="skills">{t("resume.skills")}</TabsTrigger>
          <TabsTrigger value="experience">{t("resume.experiences")}</TabsTrigger>
        </TabsList>
        <TabsContent value="basics"><BasicsTab /></TabsContent>
        <TabsContent value="skills"><SkillsTab /></TabsContent>
        <TabsContent value="experience"><ExperienceTab /></TabsContent>
      </Tabs>
    </div>
  );
}

function BasicsTab() {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const { data, isLoading } = useQuery({ queryKey: ["resume-basics"], queryFn: () => listResumeBasics() });
  const existing = data?.items?.[0];
  const [form, setForm] = useState({ title: "", subtitle: "", summary: "", download_label: "" });

  useEffect(() => {
    if (existing) setForm({ title: existing.title, subtitle: existing.subtitle, summary: existing.summary, download_label: existing.download_label });
  }, [existing]);

  const save = useMutation({
    mutationFn: () => existing
      ? updateResumeBasics(existing.id, form)
      : createResumeBasics(form),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["resume-basics"] }),
  });

  if (isLoading) return <p className="py-4 text-muted-foreground">{t("common.loading")}</p>;

  const fieldLabels: Record<string, string> = {
    title: t("common.title"),
    subtitle: t("resume.subtitle"),
    download_label: t("resume.downloadLabel"),
  };

  return (
    <Card className="mt-4 max-w-2xl">
      <CardContent className="pt-6 space-y-4">
        {(["title", "subtitle", "download_label"] as const).map((k) => (
          <div key={k} className="space-y-2">
            <Label>{fieldLabels[k]}</Label>
            <Input value={form[k]} onChange={(e) => setForm((p) => ({ ...p, [k]: e.target.value }))} />
          </div>
        ))}
        <div className="space-y-2">
          <Label>{t("resume.summary")}</Label>
          <Textarea value={form.summary} onChange={(e) => setForm((p) => ({ ...p, summary: e.target.value }))} rows={4} />
        </div>
        <Button onClick={() => save.mutate()} disabled={save.isPending}>
          <Save className="h-4 w-4 mr-2" /> {save.isPending ? t("common.saving") : t("common.save")}
        </Button>
      </CardContent>
    </Card>
  );
}

function SkillsTab() {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const { data: basicsData } = useQuery({ queryKey: ["resume-basics"], queryFn: () => listResumeBasics() });
  const { data } = useQuery({ queryKey: ["resume-skills"], queryFn: () => listResumeSkills() });
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ category: "", items: "" as any, order_index: 0 });

  const basicsId = basicsData?.items?.[0]?.id ?? "";

  const create = useMutation({
    mutationFn: () => createResumeSkill({ resume_basics_id: basicsId, category: form.category, items: form.items.split(",").map((s: string) => s.trim()).filter(Boolean), order_index: form.order_index }),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["resume-skills"] }); setOpen(false); setForm({ category: "", items: "", order_index: 0 }); },
  });

  const del = useMutation({
    mutationFn: (id: string) => deleteResumeSkill(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["resume-skills"] }),
  });

  return (
    <div className="mt-4">
      <div className="flex justify-end mb-4">
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild><Button disabled={!basicsId}><Plus className="h-4 w-4 mr-2" /> {t("resume.addSkillGroup")}</Button></DialogTrigger>
          <DialogContent>
            <DialogHeader><DialogTitle>{t("resume.newSkillGroup")}</DialogTitle></DialogHeader>
            <div className="space-y-3">
              <div className="space-y-1"><Label>{t("resume.category")}</Label><Input value={form.category} onChange={(e) => setForm((p) => ({ ...p, category: e.target.value }))} /></div>
              <div className="space-y-1"><Label>{t("resume.itemsCommaSeparated")}</Label><Input value={form.items} onChange={(e) => setForm((p) => ({ ...p, items: e.target.value }))} /></div>
              <div className="space-y-1"><Label>{t("common.order")}</Label><Input type="number" value={form.order_index} onChange={(e) => setForm((p) => ({ ...p, order_index: parseInt(e.target.value) || 0 }))} /></div>
              <Button onClick={() => create.mutate()} disabled={create.isPending}>{t("common.create")}</Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>
      {!basicsId && <p className="text-sm text-muted-foreground mb-2">{t("resume.saveBasicsFirst")}</p>}
      <div className="border rounded-lg">
        <DataTable<ResumeSkillGroup>
          columns={[
            { header: t("resume.category"), accessor: "category" },
            { header: t("common.items"), accessor: (row) => row.items.join(", ") },
            { header: t("common.order"), accessor: "order_index" as any },
            { header: "", accessor: (row) => <Button variant="ghost" size="icon" onClick={() => del.mutate(row.id)}><Trash2 className="h-4 w-4" /></Button> },
          ]}
          data={data?.items ?? []}
          total={data?.total ?? 0}
        />
      </div>
    </div>
  );
}

function ExperienceTab() {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const { data: basicsData } = useQuery({ queryKey: ["resume-basics"], queryFn: () => listResumeBasics() });
  const { data } = useQuery({ queryKey: ["resume-experiences"], queryFn: () => listResumeExperiences() });
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ title: "", company: "", period: "", summary: "", order_index: 0 });

  const basicsId = basicsData?.items?.[0]?.id ?? "";

  const create = useMutation({
    mutationFn: () => createResumeExperience({ resume_basics_id: basicsId, ...form }),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["resume-experiences"] }); setOpen(false); setForm({ title: "", company: "", period: "", summary: "", order_index: 0 }); },
  });

  const del = useMutation({
    mutationFn: (id: string) => deleteResumeExperience(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["resume-experiences"] }),
  });

  const fieldLabels: Record<string, string> = {
    title: t("common.title"),
    company: t("resume.company"),
    period: t("resume.period"),
  };

  return (
    <div className="mt-4">
      <div className="flex justify-end mb-4">
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild><Button disabled={!basicsId}><Plus className="h-4 w-4 mr-2" /> {t("resume.addExperience")}</Button></DialogTrigger>
          <DialogContent>
            <DialogHeader><DialogTitle>{t("resume.newExperience")}</DialogTitle></DialogHeader>
            <div className="space-y-3">
              {(["title", "company", "period"] as const).map((k) => (
                <div key={k} className="space-y-1"><Label>{fieldLabels[k]}</Label><Input value={form[k]} onChange={(e) => setForm((p) => ({ ...p, [k]: e.target.value }))} /></div>
              ))}
              <div className="space-y-1"><Label>{t("resume.summary")}</Label><Textarea value={form.summary} onChange={(e) => setForm((p) => ({ ...p, summary: e.target.value }))} rows={3} /></div>
              <div className="space-y-1"><Label>{t("common.order")}</Label><Input type="number" value={form.order_index} onChange={(e) => setForm((p) => ({ ...p, order_index: parseInt(e.target.value) || 0 }))} /></div>
              <Button onClick={() => create.mutate()} disabled={create.isPending}>{t("common.create")}</Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>
      {!basicsId && <p className="text-sm text-muted-foreground mb-2">{t("resume.saveBasicsFirstExp")}</p>}
      <div className="border rounded-lg">
        <DataTable<ResumeExperience>
          columns={[
            { header: t("common.title"), accessor: "title" },
            { header: t("resume.company"), accessor: "company" },
            { header: t("resume.period"), accessor: "period" },
            { header: t("common.order"), accessor: "order_index" as any },
            { header: "", accessor: (row) => <Button variant="ghost" size="icon" onClick={() => del.mutate(row.id)}><Trash2 className="h-4 w-4" /></Button> },
          ]}
          data={data?.items ?? []}
          total={data?.total ?? 0}
        />
      </div>
    </div>
  );
}
