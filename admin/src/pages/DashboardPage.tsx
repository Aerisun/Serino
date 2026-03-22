import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { getDashboardStats } from "@/api/endpoints/system";
import { PageHeader } from "@/components/PageHeader";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/Card";
import { StatusBadge } from "@/components/StatusBadge";
import { FileText, BookOpen, Lightbulb, Quote, MessageSquare, Users, Image, Clock } from "lucide-react";
import { useI18n } from "@/i18n";
import type { EnhancedDashboardStats, RecentContentItem } from "@/types/models";

const CONTENT_TYPE_ROUTES: Record<string, string> = {
  post: "/posts",
  diary: "/diary",
  thought: "/thoughts",
  excerpt: "/excerpts",
};

export default function DashboardPage() {
  const { t } = useI18n();
  const navigate = useNavigate();

  const { data: stats, isLoading } = useQuery<EnhancedDashboardStats>({
    queryKey: ["dashboard-stats"],
    queryFn: getDashboardStats,
  });

  if (isLoading || !stats) {
    return (
      <div>
        <PageHeader title={t("dashboard.title")} description={t("dashboard.description")} />
        <p className="text-muted-foreground">{t("common.loading")}</p>
      </div>
    );
  }

  const statCards = [
    { label: t("nav.posts"), value: stats.posts, icon: FileText, color: "text-blue-500" },
    { label: t("nav.diary"), value: stats.diary_entries, icon: BookOpen, color: "text-green-500" },
    { label: t("nav.thoughts"), value: stats.thoughts, icon: Lightbulb, color: "text-yellow-500" },
    { label: t("nav.excerpts"), value: stats.excerpts, icon: Quote, color: "text-purple-500" },
    { label: t("nav.moderation"), value: stats.comments, icon: MessageSquare, color: "text-orange-500" },
    { label: t("nav.friends"), value: stats.friends, icon: Users, color: "text-pink-500" },
    { label: t("nav.assets"), value: stats.assets, icon: Image, color: "text-cyan-500" },
  ];

  const formatDate = (dateStr: string) => {
    const d = new Date(dateStr);
    return d.toLocaleDateString() + " " + d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  };

  const contentTypeLabel = (type: string) => {
    const map: Record<string, string> = { post: t("nav.posts"), diary: t("nav.diary"), thought: t("nav.thoughts"), excerpt: t("nav.excerpts") };
    return map[type] || type;
  };

  return (
    <div>
      <PageHeader title={t("dashboard.title")} description={t("dashboard.description")} />

      {/* Stat cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-4 mb-8">
        {statCards.map((card) => (
          <Card key={card.label}>
            <CardContent className="pt-4 pb-4 px-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs text-muted-foreground">{card.label}</p>
                  <p className="text-2xl font-bold">{card.value}</p>
                </div>
                <card.icon className={`h-5 w-5 ${card.color}`} />
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Posts by Status */}
        {stats.posts_by_status && Object.keys(stats.posts_by_status).length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle className="text-base">{t("dashboard.postsByStatus")}</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {Object.entries(stats.posts_by_status).map(([status, count]) => {
                  const total = stats.posts || 1;
                  const pct = Math.round((count / total) * 100);
                  return (
                    <div key={status} className="flex items-center gap-3">
                      <StatusBadge status={status} />
                      <div className="flex-1 h-2 rounded-full bg-muted overflow-hidden">
                        <div
                          className="h-full rounded-full bg-primary transition-all"
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                      <span className="text-sm text-muted-foreground w-12 text-right">{count}</span>
                    </div>
                  );
                })}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Monthly trend */}
        {stats.content_by_month && stats.content_by_month.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle className="text-base">{t("dashboard.monthlyTrend")}</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                {stats.content_by_month.map((m) => {
                  const total = m.posts + m.diary + m.thoughts + m.excerpts;
                  return (
                    <div key={m.month} className="flex items-center gap-3">
                      <span className="text-sm text-muted-foreground w-20">{m.month}</span>
                      <div className="flex-1 flex gap-0.5 h-4">
                        {m.posts > 0 && <div className="bg-blue-500 rounded-sm" style={{ flex: m.posts }} title={`Posts: ${m.posts}`} />}
                        {m.diary > 0 && <div className="bg-green-500 rounded-sm" style={{ flex: m.diary }} title={`Diary: ${m.diary}`} />}
                        {m.thoughts > 0 && <div className="bg-yellow-500 rounded-sm" style={{ flex: m.thoughts }} title={`Thoughts: ${m.thoughts}`} />}
                        {m.excerpts > 0 && <div className="bg-purple-500 rounded-sm" style={{ flex: m.excerpts }} title={`Excerpts: ${m.excerpts}`} />}
                      </div>
                      <span className="text-sm text-muted-foreground w-8 text-right">{total}</span>
                    </div>
                  );
                })}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Recent Content */}
        {stats.recent_content && stats.recent_content.length > 0 && (
          <Card className="lg:col-span-2">
            <CardHeader>
              <CardTitle className="text-base">{t("dashboard.recentContent")}</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                {stats.recent_content.map((item: RecentContentItem) => (
                  <div
                    key={item.id}
                    className="flex items-center justify-between rounded-lg border p-3 cursor-pointer hover:bg-accent/50 transition-colors"
                    onClick={() => navigate(`${CONTENT_TYPE_ROUTES[item.content_type] || "/posts"}/${item.id}`)}
                  >
                    <div className="flex items-center gap-3">
                      <span className="text-xs px-2 py-0.5 rounded bg-muted">{contentTypeLabel(item.content_type)}</span>
                      <span className="text-sm font-medium">{item.title}</span>
                    </div>
                    <div className="flex items-center gap-3">
                      <StatusBadge status={item.status} />
                      <span className="text-xs text-muted-foreground flex items-center gap-1">
                        <Clock className="h-3 w-3" /> {formatDate(item.updated_at)}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
