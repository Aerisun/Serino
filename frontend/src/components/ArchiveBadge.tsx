import { useFrontendI18n } from "@/i18n";

interface ArchiveBadgeProps {
  className?: string;
}

const ArchiveBadge = ({ className = "" }: ArchiveBadgeProps) => {
  const { t } = useFrontendI18n();

  return (
    <span
      className={`inline-flex items-center rounded-full border border-amber-500/18 bg-amber-500/8 px-2 py-0.5 text-[10px] font-medium tracking-[0.14em] text-amber-700/78 ${className}`.trim()}
    >
      {t("content.archived")}
    </span>
  );
};

export default ArchiveBadge;
