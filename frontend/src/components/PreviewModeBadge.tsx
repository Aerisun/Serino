import { useFrontendI18n } from "@/i18n";

export default function PreviewModeBadge() {
  const { t } = useFrontendI18n();
  return (
    <div className="pointer-events-none fixed left-4 top-4 z-[9999] sm:left-6 sm:top-6">
      <div
        className="inline-flex items-center gap-2.5 rounded-full border border-amber-400/30 bg-[rgba(36,28,12,0.78)] px-4 py-2 text-xs font-medium text-amber-100 shadow-[0_12px_40px_rgba(0,0,0,0.22)] backdrop-blur-md sm:text-sm"
        aria-label={t("preview.description")}
        title={t("preview.description")}
      >
        <span className="h-2 w-2 rounded-full bg-amber-300 shadow-[0_0_10px_rgba(252,211,77,0.9)]" />
        <span>{t("preview.badge")}</span>
      </div>
    </div>
  );
}
