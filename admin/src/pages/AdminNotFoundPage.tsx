import { useMemo } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { ArrowLeft, Home } from "lucide-react";
import { PageHeader } from "@/components/PageHeader";
import { Button } from "@/components/ui/Button";
import { useI18n } from "@/i18n";

const COPY = {
  zh: {
    title: "这个后台路径不存在",
    description: "当前访问的地址不是受支持的管理后台规范路由，已移除的旧路径不会再自动跳转。",
    requestedLabel: "当前路径",
    homeLabel: "返回仪表盘",
    backLabel: "返回上页",
  },
  en: {
    title: "This admin route does not exist",
    description:
      "The requested URL is not part of the supported admin route set. Removed legacy paths no longer redirect automatically.",
    requestedLabel: "Requested path",
    homeLabel: "Back to dashboard",
    backLabel: "Go back",
  },
} as const;

export default function AdminNotFoundPage() {
  const { lang } = useI18n();
  const navigate = useNavigate();
  const location = useLocation();
  const copy = COPY[lang];

  const requestedPath = useMemo(() => {
    const search = location.search || "";
    const hash = location.hash || "";
    return `${location.pathname}${search}${hash}`;
  }, [location.hash, location.pathname, location.search]);

  return (
    <div>
      <PageHeader
        title={copy.title}
        description={copy.description}
        actions={
          <>
            <Button type="button" variant="outline" onClick={() => navigate(-1)}>
              <ArrowLeft className="mr-2 h-4 w-4" />
              {copy.backLabel}
            </Button>
            <Button type="button" onClick={() => navigate("/")}>
              <Home className="mr-2 h-4 w-4" />
              {copy.homeLabel}
            </Button>
          </>
        }
      />
      <div className="admin-glass rounded-[var(--admin-radius-xl)] px-6 py-5">
        <div className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground/80">
          {copy.requestedLabel}
        </div>
        <div className="mt-3 break-all rounded-[var(--admin-radius-lg)] border border-border/60 bg-background/65 px-4 py-3 font-mono text-sm text-foreground/80">
          {requestedPath}
        </div>
      </div>
    </div>
  );
}
