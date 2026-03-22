import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getProfile, updateProfile,
  listSocialLinks, createSocialLink, updateSocialLink, deleteSocialLink,
  listPoems, createPoem, updatePoem, deletePoem,
  listPageCopy, createPageCopy, updatePageCopy, deletePageCopy,
  listDisplayOptions, createDisplayOption, updateDisplayOption, deleteDisplayOption,
  listNavItems, createNavItem, updateNavItem, deleteNavItem,
} from "@/api/endpoints/site-config";
import { PageHeader } from "@/components/PageHeader";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/Tabs";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Textarea } from "@/components/ui/Textarea";
import { Label } from "@/components/ui/Label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { DataTable } from "@/components/DataTable";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/Dialog";
import { Plus, Save, Trash2, Pencil, X } from "lucide-react";
import { formatDate } from "@/lib/utils";
import { useI18n } from "@/i18n";
import type { SiteProfile, SocialLink, Poem, PageCopy, PageDisplayOption, NavItem } from "@/types/models";

const PAGE_KEYS = ["posts", "diary", "friends", "excerpts", "thoughts", "guestbook", "resume", "calendar"];

export default function SiteConfigPage() {
  const { t } = useI18n();
  return (
    <div>
      <PageHeader title={t("siteConfig.title")} description={t("siteConfig.description")} />
      <Tabs defaultValue="profile">
        <TabsList>
          <TabsTrigger value="profile">{t("siteConfig.profile")}</TabsTrigger>
          <TabsTrigger value="social">{t("siteConfig.socialLinks")}</TabsTrigger>
          <TabsTrigger value="poems">{t("siteConfig.poems")}</TabsTrigger>
          <TabsTrigger value="pages">{t("siteConfig.pages")}</TabsTrigger>
          <TabsTrigger value="nav">导航菜单</TabsTrigger>
        </TabsList>

        <TabsContent value="profile"><ProfileTab /></TabsContent>
        <TabsContent value="social"><SocialLinksTab /></TabsContent>
        <TabsContent value="poems"><PoemsTab /></TabsContent>
        <TabsContent value="pages"><PagesTab /></TabsContent>
        <TabsContent value="nav"><NavItemsTab /></TabsContent>
      </Tabs>
    </div>
  );
}

function ProfileTab() {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const { data: profile, isLoading } = useQuery({ queryKey: ["site-profile"], queryFn: getProfile });
  const [form, setForm] = useState({ name: "", title: "", bio: "", role: "", footer_text: "", hero_video_url: "" });

  useEffect(() => {
    if (profile) setForm({ name: profile.name, title: profile.title, bio: profile.bio, role: profile.role, footer_text: profile.footer_text, hero_video_url: profile.hero_video_url || "" });
  }, [profile]);

  const save = useMutation({
    mutationFn: () => updateProfile(form),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["site-profile"] }),
  });

  if (isLoading) return <p className="py-4 text-muted-foreground">{t("common.loading")}</p>;

  const fieldLabels: Record<string, string> = {
    name: t("siteConfig.siteName"),
    title: t("siteConfig.siteTitle"),
    role: t("siteConfig.role"),
    footer_text: t("siteConfig.footerText"),
    hero_video_url: "首页视频 URL",
  };

  return (
    <Card className="mt-4 max-w-2xl">
      <CardContent className="pt-6 space-y-4">
        {(["name", "title", "role", "footer_text", "hero_video_url"] as const).map((key) => (
          <div key={key} className="space-y-2">
            <Label>{fieldLabels[key]}</Label>
            <Input value={form[key]} onChange={(e) => setForm((p) => ({ ...p, [key]: e.target.value }))} />
          </div>
        ))}
        <div className="space-y-2">
          <Label>{t("siteConfig.bio")}</Label>
          <Textarea value={form.bio} onChange={(e) => setForm((p) => ({ ...p, bio: e.target.value }))} rows={4} />
        </div>
        <Button onClick={() => save.mutate()} disabled={save.isPending}>
          <Save className="h-4 w-4 mr-2" /> {save.isPending ? t("common.saving") : t("common.save")}
        </Button>
      </CardContent>
    </Card>
  );
}

function SocialLinksTab() {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const { data: profile } = useQuery({ queryKey: ["site-profile"], queryFn: getProfile });
  const { data } = useQuery({ queryKey: ["social-links"], queryFn: () => listSocialLinks() });
  const [open, setOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState({ name: "", href: "", icon_key: "", placement: "hero", order_index: 0 });

  const profileId = profile?.id ?? "";

  const create = useMutation({
    mutationFn: () => createSocialLink({ ...form, site_profile_id: profileId }),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["social-links"] }); setOpen(false); resetForm(); },
  });

  const update = useMutation({
    mutationFn: () => updateSocialLink(editingId!, form),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["social-links"] }); setEditingId(null); setOpen(false); resetForm(); },
  });

  const del = useMutation({
    mutationFn: (id: string) => deleteSocialLink(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["social-links"] }),
  });

  function resetForm() {
    setForm({ name: "", href: "", icon_key: "", placement: "hero", order_index: 0 });
  }

  function startEdit(link: SocialLink) {
    setEditingId(link.id);
    setForm({ name: link.name, href: link.href, icon_key: link.icon_key, placement: link.placement, order_index: link.order_index });
    setOpen(true);
  }

  const fieldLabels: Record<string, string> = {
    name: t("siteConfig.name"),
    href: t("siteConfig.href"),
    icon_key: t("siteConfig.iconKey"),
    placement: t("siteConfig.placement"),
  };

  return (
    <div className="mt-4">
      <div className="flex justify-end mb-4">
        <Dialog open={open} onOpenChange={(v) => { setOpen(v); if (!v) { setEditingId(null); resetForm(); } }}>
          <DialogTrigger asChild><Button><Plus className="h-4 w-4 mr-2" /> {t("siteConfig.addLink")}</Button></DialogTrigger>
          <DialogContent>
            <DialogHeader><DialogTitle>{editingId ? t("siteConfig.editSocialLink") : t("siteConfig.newSocialLink")}</DialogTitle></DialogHeader>
            <div className="space-y-3">
              {(["name", "href", "icon_key", "placement"] as const).map((k) => (
                <div key={k} className="space-y-1">
                  <Label>{fieldLabels[k]}</Label>
                  <Input value={(form as any)[k]} onChange={(e) => setForm((p) => ({ ...p, [k]: e.target.value }))} />
                </div>
              ))}
              <div className="space-y-1">
                <Label>{t("common.order")}</Label>
                <Input type="number" value={form.order_index} onChange={(e) => setForm((p) => ({ ...p, order_index: parseInt(e.target.value) || 0 }))} />
              </div>
              <Button onClick={() => editingId ? update.mutate() : create.mutate()} disabled={create.isPending || update.isPending}>
                {editingId ? t("common.save") : t("common.create")}
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>
      <div className="border rounded-lg">
        <DataTable<SocialLink>
          columns={[
            { header: t("siteConfig.name"), accessor: "name" },
            { header: t("siteConfig.url"), accessor: "href" },
            { header: t("siteConfig.icon"), accessor: "icon_key" },
            { header: t("siteConfig.placement"), accessor: "placement" },
            { header: t("common.order"), accessor: "order_index" as any },
            { header: "", accessor: (row) => (
              <div className="flex gap-1">
                <Button variant="ghost" size="icon" onClick={(e) => { e.stopPropagation(); startEdit(row); }}><Pencil className="h-4 w-4" /></Button>
                <Button variant="ghost" size="icon" onClick={(e) => { e.stopPropagation(); del.mutate(row.id); }}><Trash2 className="h-4 w-4" /></Button>
              </div>
            )},
          ]}
          data={data?.items ?? []}
          total={data?.total ?? 0}
        />
      </div>
    </div>
  );
}

function PoemsTab() {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const { data: profile } = useQuery({ queryKey: ["site-profile"], queryFn: getProfile });
  const { data } = useQuery({ queryKey: ["poems"], queryFn: () => listPoems() });
  const [open, setOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState({ content: "", order_index: 0 });

  const profileId = profile?.id ?? "";

  const create = useMutation({
    mutationFn: () => createPoem({ ...form, site_profile_id: profileId }),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["poems"] }); setOpen(false); resetForm(); },
  });

  const update = useMutation({
    mutationFn: () => updatePoem(editingId!, form),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["poems"] }); setEditingId(null); setOpen(false); resetForm(); },
  });

  const del = useMutation({
    mutationFn: (id: string) => deletePoem(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["poems"] }),
  });

  function resetForm() {
    setForm({ content: "", order_index: 0 });
  }

  function startEdit(poem: Poem) {
    setEditingId(poem.id);
    setForm({ content: poem.content, order_index: poem.order_index });
    setOpen(true);
  }

  return (
    <div className="mt-4">
      <div className="flex justify-end mb-4">
        <Dialog open={open} onOpenChange={(v) => { setOpen(v); if (!v) { setEditingId(null); resetForm(); } }}>
          <DialogTrigger asChild><Button><Plus className="h-4 w-4 mr-2" /> {t("siteConfig.addPoem")}</Button></DialogTrigger>
          <DialogContent>
            <DialogHeader><DialogTitle>{editingId ? t("siteConfig.editPoem") : t("siteConfig.newPoem")}</DialogTitle></DialogHeader>
            <div className="space-y-3">
              <div className="space-y-1"><Label>{t("siteConfig.content")}</Label><Textarea value={form.content} onChange={(e) => setForm((p) => ({ ...p, content: e.target.value }))} rows={4} /></div>
              <div className="space-y-1"><Label>{t("common.order")}</Label><Input type="number" value={form.order_index} onChange={(e) => setForm((p) => ({ ...p, order_index: parseInt(e.target.value) || 0 }))} /></div>
              <Button onClick={() => editingId ? update.mutate() : create.mutate()} disabled={create.isPending || update.isPending}>
                {editingId ? t("common.save") : t("common.create")}
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>
      <div className="border rounded-lg">
        <DataTable<Poem>
          columns={[
            { header: t("siteConfig.content"), accessor: (row) => <span className="line-clamp-2">{row.content}</span> },
            { header: t("common.order"), accessor: "order_index" as any },
            { header: "", accessor: (row) => (
              <div className="flex gap-1">
                <Button variant="ghost" size="icon" onClick={(e) => { e.stopPropagation(); startEdit(row); }}><Pencil className="h-4 w-4" /></Button>
                <Button variant="ghost" size="icon" onClick={(e) => { e.stopPropagation(); del.mutate(row.id); }}><Trash2 className="h-4 w-4" /></Button>
              </div>
            )},
          ]}
          data={data?.items ?? []}
          total={data?.total ?? 0}
        />
      </div>
    </div>
  );
}

function PagesTab() {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const { data: copyData } = useQuery({ queryKey: ["page-copy"], queryFn: () => listPageCopy() });
  const { data: displayData } = useQuery({ queryKey: ["display-options"], queryFn: () => listDisplayOptions() });

  const [createOpen, setCreateOpen] = useState(false);
  const [createForm, setCreateForm] = useState({
    page_key: "", title: "", subtitle: "", label: "", description: "", search_placeholder: "", empty_message: "", page_size: "" as string,
  });

  const createCopy = useMutation({
    mutationFn: () => createPageCopy({
      page_key: createForm.page_key,
      title: createForm.title,
      subtitle: createForm.subtitle,
      label: createForm.label || null,
      description: createForm.description || null,
      search_placeholder: createForm.search_placeholder || null,
      empty_message: createForm.empty_message || null,
      page_size: createForm.page_size ? parseInt(createForm.page_size) : null,
    }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["page-copy"] });
      setCreateOpen(false);
      setCreateForm({ page_key: "", title: "", subtitle: "", label: "", description: "", search_placeholder: "", empty_message: "", page_size: "" });
    },
  });

  const createDisplay = useMutation({
    mutationFn: (page_key: string) => createDisplayOption({ page_key }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["display-options"] }),
  });

  // Merge copy + display by page_key
  const copies = copyData?.items ?? [];
  const displays = displayData?.items ?? [];
  const displayByKey = Object.fromEntries(displays.map((d) => [d.page_key, d]));
  const allKeys = Array.from(new Set([...copies.map((c) => c.page_key), ...displays.map((d) => d.page_key)]));

  const formFieldLabels: Record<string, string> = {
    title: t("common.title"),
    subtitle: t("siteConfig.subtitle"),
    label: t("siteConfig.label"),
    description: t("siteConfig.description2"),
    search_placeholder: t("siteConfig.searchPlaceholder"),
    empty_message: t("siteConfig.emptyMessage"),
  };

  return (
    <div className="mt-4 space-y-4">
      <div className="flex justify-end">
        <Dialog open={createOpen} onOpenChange={setCreateOpen}>
          <DialogTrigger asChild><Button><Plus className="h-4 w-4 mr-2" /> {t("siteConfig.addPage")}</Button></DialogTrigger>
          <DialogContent className="max-w-lg">
            <DialogHeader><DialogTitle>{t("siteConfig.newPageCopy")}</DialogTitle></DialogHeader>
            <div className="space-y-3">
              <div className="space-y-1">
                <Label>{t("siteConfig.pageKey")}</Label>
                <select
                  className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                  value={createForm.page_key}
                  onChange={(e) => setCreateForm((p) => ({ ...p, page_key: e.target.value }))}
                >
                  <option value="">{t("siteConfig.selectPage")}</option>
                  {PAGE_KEYS.map((k) => <option key={k} value={k}>{k}</option>)}
                </select>
              </div>
              {(["title", "subtitle", "label", "description", "search_placeholder", "empty_message"] as const).map((k) => (
                <div key={k} className="space-y-1">
                  <Label>{formFieldLabels[k]}</Label>
                  <Input value={createForm[k]} onChange={(e) => setCreateForm((p) => ({ ...p, [k]: e.target.value }))} />
                </div>
              ))}
              <div className="space-y-1">
                <Label>{t("siteConfig.pageSize")}</Label>
                <Input type="number" value={createForm.page_size} onChange={(e) => setCreateForm((p) => ({ ...p, page_size: e.target.value }))} />
              </div>
              <Button onClick={() => createCopy.mutate()} disabled={createCopy.isPending || !createForm.page_key}>{t("common.create")}</Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      {copies.length === 0 && displays.length === 0 && (
        <p className="text-muted-foreground py-4">{t("siteConfig.noPages")}</p>
      )}

      {copies.map((copy) => (
        <PageRow key={copy.id} copy={copy} display={displayByKey[copy.page_key]} />
      ))}
    </div>
  );
}

function PageRow({ copy, display }: { copy: PageCopy; display?: PageDisplayOption }) {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState({
    title: copy.title, subtitle: copy.subtitle, label: copy.label ?? "",
    description: copy.description ?? "", search_placeholder: copy.search_placeholder ?? "",
    empty_message: copy.empty_message ?? "", page_size: copy.page_size?.toString() ?? "",
  });
  const [settingsJson, setSettingsJson] = useState(display ? JSON.stringify(display.settings, null, 2) : "{}");

  const saveCopy = useMutation({
    mutationFn: () => updatePageCopy(copy.id, {
      title: form.title, subtitle: form.subtitle,
      label: form.label || null, description: form.description || null,
      search_placeholder: form.search_placeholder || null,
      empty_message: form.empty_message || null,
      page_size: form.page_size ? parseInt(form.page_size) : null,
    }),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["page-copy"] }); setEditing(false); },
  });

  const toggleEnabled = useMutation({
    mutationFn: () => {
      if (display) return updateDisplayOption(display.id, { is_enabled: !display.is_enabled });
      return createDisplayOption({ page_key: copy.page_key, is_enabled: true });
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["display-options"] }),
  });

  const saveSettings = useMutation({
    mutationFn: () => {
      const parsed = JSON.parse(settingsJson);
      if (display) return updateDisplayOption(display.id, { settings: parsed });
      return createDisplayOption({ page_key: copy.page_key, settings: parsed });
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["display-options"] }),
  });

  const delCopy = useMutation({
    mutationFn: () => deletePageCopy(copy.id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["page-copy"] }),
  });

  const formFieldLabels: Record<string, string> = {
    title: t("common.title"),
    subtitle: t("siteConfig.subtitle"),
    label: t("siteConfig.label"),
    description: t("siteConfig.description2"),
    search_placeholder: t("siteConfig.searchPlaceholder"),
    empty_message: t("siteConfig.emptyMessage"),
  };

  const displayLabels: Record<string, string> = {
    Title: t("common.title"),
    Subtitle: t("siteConfig.subtitle"),
    Label: t("siteConfig.label"),
    Description: t("siteConfig.description2"),
    "Search placeholder": t("siteConfig.searchPlaceholder"),
    "Empty message": t("siteConfig.emptyMessage"),
    "Page size": t("siteConfig.pageSize"),
  };

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="text-base font-semibold">{copy.page_key}</CardTitle>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => toggleEnabled.mutate()}>
            {display?.is_enabled !== false ? t("siteConfig.enabled") : t("siteConfig.disabled")}
          </Button>
          <Button variant="ghost" size="icon" onClick={() => setEditing(!editing)}>
            {editing ? <X className="h-4 w-4" /> : <Pencil className="h-4 w-4" />}
          </Button>
          <Button variant="ghost" size="icon" onClick={() => { if (confirm(t("siteConfig.deletePageConfirm"))) delCopy.mutate(); }}>
            <Trash2 className="h-4 w-4" />
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        {!editing ? (
          <div className="grid grid-cols-2 gap-x-6 gap-y-1 text-sm">
            <div><span className="text-muted-foreground">{t("common.title")}:</span> {copy.title}</div>
            <div><span className="text-muted-foreground">{t("siteConfig.subtitle")}:</span> {copy.subtitle}</div>
            {copy.label && <div><span className="text-muted-foreground">{t("siteConfig.label")}:</span> {copy.label}</div>}
            {copy.description && <div><span className="text-muted-foreground">{t("siteConfig.description2")}:</span> {copy.description}</div>}
            {copy.search_placeholder && <div><span className="text-muted-foreground">{t("siteConfig.searchPlaceholder")}:</span> {copy.search_placeholder}</div>}
            {copy.empty_message && <div><span className="text-muted-foreground">{t("siteConfig.emptyMessage")}:</span> {copy.empty_message}</div>}
            {copy.page_size != null && <div><span className="text-muted-foreground">{t("siteConfig.pageSize")}:</span> {copy.page_size}</div>}
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-3">
              {(["title", "subtitle", "label", "description", "search_placeholder", "empty_message"] as const).map((k) => (
                <div key={k} className="space-y-1">
                  <Label className="text-xs">{formFieldLabels[k]}</Label>
                  <Input value={form[k]} onChange={(e) => setForm((p) => ({ ...p, [k]: e.target.value }))} />
                </div>
              ))}
              <div className="space-y-1">
                <Label className="text-xs">{t("siteConfig.pageSize")}</Label>
                <Input type="number" value={form.page_size} onChange={(e) => setForm((p) => ({ ...p, page_size: e.target.value }))} />
              </div>
              <Button size="sm" onClick={() => saveCopy.mutate()} disabled={saveCopy.isPending}>
                <Save className="h-3 w-3 mr-1" /> {t("siteConfig.saveCopy")}
              </Button>
            </div>
            <div className="space-y-3">
              <div className="space-y-1">
                <Label className="text-xs">{t("siteConfig.settingsJson")}</Label>
                <Textarea value={settingsJson} onChange={(e) => setSettingsJson(e.target.value)} rows={8} className="font-mono text-xs" />
              </div>
              <Button size="sm" onClick={() => saveSettings.mutate()} disabled={saveSettings.isPending}>
                <Save className="h-3 w-3 mr-1" /> {t("siteConfig.saveSettings")}
              </Button>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function NavItemsTab() {
  const queryClient = useQueryClient();
  const { data } = useQuery({ queryKey: ["nav-items"], queryFn: () => listNavItems() });
  const [open, setOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState({ label: "", href: "", trigger: "", page_key: "", parent_id: "", order_index: 0, is_enabled: true });

  const items = data?.items ?? [];
  const topLevel = items.filter((i) => !i.parent_id).sort((a, b) => a.order_index - b.order_index);
  const childrenOf = (pid: string) => items.filter((i) => i.parent_id === pid).sort((a, b) => a.order_index - b.order_index);

  const create = useMutation({
    mutationFn: () => createNavItem({
      ...form,
      trigger: form.trigger || null,
      page_key: form.page_key || null,
      parent_id: form.parent_id || null,
    }),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["nav-items"] }); setOpen(false); resetForm(); },
  });

  const update = useMutation({
    mutationFn: () => updateNavItem(editingId!, {
      ...form,
      trigger: form.trigger || null,
      page_key: form.page_key || null,
      parent_id: form.parent_id || null,
    }),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["nav-items"] }); setEditingId(null); setOpen(false); resetForm(); },
  });

  const del = useMutation({
    mutationFn: (id: string) => deleteNavItem(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["nav-items"] }),
  });

  function resetForm() {
    setForm({ label: "", href: "", trigger: "", page_key: "", parent_id: "", order_index: 0, is_enabled: true });
  }

  function startEdit(item: NavItem) {
    setEditingId(item.id);
    setForm({
      label: item.label, href: item.href, trigger: item.trigger || "", page_key: item.page_key || "",
      parent_id: item.parent_id || "", order_index: item.order_index, is_enabled: item.is_enabled,
    });
    setOpen(true);
  }

  function renderItem(item: NavItem, depth: number = 0) {
    const children = childrenOf(item.id);
    return (
      <div key={item.id}>
        <div className={`flex items-center gap-2 py-2 px-3 border-b hover:bg-muted/50 ${depth > 0 ? "pl-8" : ""}`}>
          <span className={`text-sm font-medium ${!item.is_enabled ? "text-muted-foreground line-through" : ""}`}>{item.label}</span>
          <span className="text-xs text-muted-foreground">{item.href}</span>
          {item.trigger && <span className="text-xs bg-blue-100 text-blue-700 px-1.5 rounded">{item.trigger}</span>}
          {item.page_key && <span className="text-xs bg-green-100 text-green-700 px-1.5 rounded">{item.page_key}</span>}
          <span className="text-xs text-muted-foreground ml-auto">#{item.order_index}</span>
          <Button variant="ghost" size="icon" onClick={() => startEdit(item)}><Pencil className="h-4 w-4" /></Button>
          <Button variant="ghost" size="icon" onClick={() => del.mutate(item.id)}><Trash2 className="h-4 w-4" /></Button>
        </div>
        {children.map((c) => renderItem(c, depth + 1))}
      </div>
    );
  }

  return (
    <div className="mt-4">
      <div className="flex justify-end mb-4">
        <Dialog open={open} onOpenChange={(v) => { setOpen(v); if (!v) { setEditingId(null); resetForm(); } }}>
          <DialogTrigger asChild><Button><Plus className="h-4 w-4 mr-2" /> 添加导航项</Button></DialogTrigger>
          <DialogContent>
            <DialogHeader><DialogTitle>{editingId ? "编辑导航项" : "新建导航项"}</DialogTitle></DialogHeader>
            <div className="space-y-3">
              <div className="space-y-1"><Label>标签</Label><Input value={form.label} onChange={(e) => setForm((p) => ({ ...p, label: e.target.value }))} /></div>
              <div className="space-y-1"><Label>链接 (href)</Label><Input value={form.href} onChange={(e) => setForm((p) => ({ ...p, href: e.target.value }))} /></div>
              <div className="space-y-1"><Label>触发器 (trigger)</Label><Input value={form.trigger} onChange={(e) => setForm((p) => ({ ...p, trigger: e.target.value }))} placeholder="可选，如 dropdown" /></div>
              <div className="space-y-1"><Label>页面键 (page_key)</Label><Input value={form.page_key} onChange={(e) => setForm((p) => ({ ...p, page_key: e.target.value }))} placeholder="可选" /></div>
              <div className="space-y-1">
                <Label>父级菜单</Label>
                <select
                  className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                  value={form.parent_id}
                  onChange={(e) => setForm((p) => ({ ...p, parent_id: e.target.value }))}
                >
                  <option value="">无 (顶级)</option>
                  {items.filter((i) => !i.parent_id && i.id !== editingId).map((i) => (
                    <option key={i.id} value={i.id}>{i.label}</option>
                  ))}
                </select>
              </div>
              <div className="space-y-1"><Label>排序</Label><Input type="number" value={form.order_index} onChange={(e) => setForm((p) => ({ ...p, order_index: parseInt(e.target.value) || 0 }))} /></div>
              <div className="flex items-center gap-2">
                <input type="checkbox" checked={form.is_enabled} onChange={(e) => setForm((p) => ({ ...p, is_enabled: e.target.checked }))} />
                <Label>启用</Label>
              </div>
              <Button onClick={() => editingId ? update.mutate() : create.mutate()} disabled={create.isPending || update.isPending}>
                {editingId ? "保存" : "创建"}
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>
      <div className="border rounded-lg">
        {topLevel.length === 0 && <p className="p-4 text-muted-foreground text-sm">暂无导航项</p>}
        {topLevel.map((item) => renderItem(item))}
      </div>
    </div>
  );
}
