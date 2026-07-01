import { AdminSectionTabs } from "@/components/ui/AdminSectionTabs";
import { Activity, Settings2, Users } from "lucide-react";

const tabs = [
  {
    value: "visitors-config",
    to: "/visitors",
    end: true,
    label: "基础配置",
    description: "访客与管理员认证",
    icon: Settings2,
  },
  {
    value: "visitors-users",
    to: "/visitors/users",
    label: "用户统计",
    description: "访客列表和参与订阅的访客邮箱",
    icon: Users,
  },
  {
    value: "visitors-monitoring",
    to: "/visitors/monitoring",
    label: "访客监控",
    description: "访问记录、设备与来源分析",
    icon: Activity,
  },
] as const;

export function VisitorsSectionSwitch() {
  return <AdminSectionTabs items={tabs} className="w-fit" />;
}
