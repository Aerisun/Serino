import { AdminSectionTabs } from "@/components/ui/AdminSectionTabs";
import { Settings2, Users } from "lucide-react";

const tabs = [
  {
    value: "visitors-config",
    to: "/visitors",
    end: true,
    label: "基础配置",
    description: "访客认证",
    icon: Settings2,
  },
  {
    value: "visitors-users",
    to: "/visitors/users",
    label: "用户统计",
    description: "访客用户",
    icon: Users,
  },
] as const;

export function VisitorsSectionSwitch() {
  return <AdminSectionTabs items={tabs} />;
}
