import { useQuery } from "@tanstack/react-query";
import { getDashboardStats } from "@/api/endpoints/system";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/Card";
import { PageHeader } from "@/components/PageHeader";
import { useI18n } from "@/i18n";
import { FileText, BookOpen, MessageSquare, Quote, Users, Image, Shield, MessageCircle, Heart, RefreshCw } from "lucide-react";

export default function DashboardPage() {
  const { t } = useI18n();

  const statConfig = [
    { key: "posts", labelKey: "dashboard.posts", icon: FileText },
    { key: "diary_entries", labelKey: "dashboard.diaryEntries", icon: BookOpen },
    { key: "thoughts", labelKey: "dashboard.thoughts", icon: MessageSquare },
    { key: "excerpts", labelKey: "dashboard.excerpts", icon: Quote },
    { key: "comments", labelKey: "dashboard.comments", icon: MessageCircle },
    { key: "guestbook_entries", labelKey: "dashboard.guestbook", icon: Shield },
    { key: "friends", labelKey: "dashboard.friends", icon: Users },
    { key: "assets", labelKey: "dashboard.assets", icon: Image },
    { key: "reactions", labelKey: "dashboard.reactions", icon: Heart },
    { key: "sync_runs", labelKey: "dashboard.syncRuns", icon: RefreshCw },
  ] as const;

  const { data: stats, isLoading } = useQuery({
    queryKey: ["dashboard-stats"],
    queryFn: getDashboardStats,
  });

  return (
    <div>
      <PageHeader title={t("dashboard.title")} description={t("dashboard.description")} />
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {statConfig.map(({ key, labelKey, icon: Icon }) => (
          <Card key={key}>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">{t(labelKey)}</CardTitle>
              <Icon className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {isLoading ? "..." : (stats?.[key] ?? 0)}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
