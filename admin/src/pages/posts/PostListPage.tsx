import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useResourceList } from "@/hooks/useResource";
import { listPosts, createPost, updatePost, deletePost } from "@/api/endpoints/posts";
import { PageHeader } from "@/components/PageHeader";
import { DataTable } from "@/components/DataTable";
import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/Tabs";
import { Plus } from "lucide-react";
import { formatDate } from "@/lib/utils";
import { useI18n } from "@/i18n";
import type { ContentItem } from "@/types/models";

export default function PostListPage() {
  const navigate = useNavigate();
  const { t } = useI18n();
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [search, setSearch] = useState("");

  const { items, total, pageSize, isLoading } = useResourceList(
    {
      queryKey: "posts",
      listFn: listPosts,
      createFn: createPost,
      updateFn: updatePost,
      deleteFn: deletePost,
    },
    { page, status: statusFilter || undefined }
  );

  const filtered = search
    ? items.filter((p) => p.title.toLowerCase().includes(search.toLowerCase()))
    : items;

  return (
    <div>
      <PageHeader
        title={t("posts.title")}
        description={t("posts.description")}
        actions={
          <Button onClick={() => navigate("/posts/new")}>
            <Plus className="h-4 w-4 mr-2" /> {t("posts.newPost")}
          </Button>
        }
      />

      <div className="flex items-center gap-4 mb-4">
        <Tabs value={statusFilter} onValueChange={(v) => { setStatusFilter(v); setPage(1); }}>
          <TabsList>
            <TabsTrigger value="">{t("common.all")}</TabsTrigger>
            <TabsTrigger value="draft">{t("posts.draft")}</TabsTrigger>
            <TabsTrigger value="published">{t("posts.published")}</TabsTrigger>
            <TabsTrigger value="archived">{t("posts.archived")}</TabsTrigger>
          </TabsList>
        </Tabs>
        <Input
          placeholder={t("posts.searchByTitle")}
          className="max-w-xs"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      <div className="border rounded-lg">
        <DataTable<ContentItem>
          columns={[
            { header: t("posts.postTitle"), accessor: "title" },
            { header: t("posts.slug"), accessor: "slug" },
            { header: t("posts.status"), accessor: (row) => <StatusBadge status={row.status} /> },
            { header: t("posts.visibility"), accessor: (row) => <StatusBadge status={row.visibility} /> },
            { header: t("posts.published"), accessor: (row) => formatDate(row.published_at) },
            { header: t("posts.updated"), accessor: (row) => formatDate(row.updated_at) },
          ]}
          data={filtered}
          total={total}
          page={page}
          pageSize={pageSize}
          onPageChange={setPage}
          isLoading={isLoading}
          onRowClick={(row) => navigate(`/posts/${row.id}`)}
        />
      </div>
    </div>
  );
}
