import { AdminSectionTabs } from "@/components/ui/AdminSectionTabs";
import { useI18n } from "@/i18n";
import { ClipboardList, GitBranch, Globe } from "lucide-react";

const COPY = {
  zh: {
    workflows: {
      label: "工作流",
    },
    activity: {
      label: "活动记录",
    },
    webhooks: {
      label: "Webhooks",
    },
  },
  en: {
    workflows: {
      label: "Workflows",
    },
    activity: {
      label: "Activity",
    },
    webhooks: {
      label: "Webhooks",
    },
  },
} as const;

export function AgentSectionSwitch() {
  const { lang } = useI18n();
  const copy = COPY[lang];

  const items = [
    {
      value: "workflows",
      to: "/agent/workflows",
      label: copy.workflows.label,
      icon: GitBranch,
    },
    {
      value: "activity",
      to: "/agent/activity",
      label: copy.activity.label,
      icon: ClipboardList,
    },
    {
      value: "webhooks",
      to: "/agent/webhooks",
      label: copy.webhooks.label,
      icon: Globe,
    },
  ] as const;

  return <AdminSectionTabs items={items} className="w-fit" />;
}
