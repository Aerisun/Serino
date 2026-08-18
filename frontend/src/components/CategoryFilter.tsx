import {
  type CSSProperties,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { Search, X } from "lucide-react";
import { useFrontendI18n } from "@/i18n";
import {
  buildCategoryFilterEntries,
  getCategoryColorIndex,
  getCategoryFilterLayout,
  getCategoryPromotion,
  type CategoryFilterEntry,
  type CategoryFilterLayout,
  type CategoryStat,
} from "@/lib/category-filter";

interface CategoryFilterStats {
  total: number;
  items: CategoryStat[];
}

interface CategoryFilterProps {
  search: string;
  searchPlaceholder: string;
  onSearchChange: (value: string) => void;
  showSearch?: boolean;
  allLabel: string;
  activeCategory: string | null;
  onCategoryChange: (category: string | null) => void;
  stats?: CategoryFilterStats;
  isLoading?: boolean;
  errorMessage?: string;
  onRetry?: () => void;
}

const CATEGORY_TINT_HUES = [
  216, 164, 52, 286, 205, 38, 122, 276, 344, 78, 238, 107,
  318, 185, 12, 252, 10, 62, 294, 145, 310, 198, 86, 250,
] as const;

export function CategoryFilter({
  search,
  searchPlaceholder,
  onSearchChange,
  showSearch = true,
  allLabel,
  activeCategory,
  onCategoryChange,
  stats,
  isLoading = false,
  errorMessage,
  onRetry,
}: CategoryFilterProps) {
  const { t } = useFrontendI18n();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [promotedCategory, setPromotedCategory] = useState<string | null>(null);
  const [layout, setLayout] = useState<CategoryFilterLayout>({
    firstRowCount: 0,
    secondRowCount: 0,
    secondRowOffset: 0,
    showMore: false,
  });
  const categoryAreaRef = useRef<HTMLDivElement | null>(null);
  const measureRef = useRef<HTMLDivElement | null>(null);
  const moreButtonRef = useRef<HTMLButtonElement | null>(null);
  const closeButtonRef = useRef<HTMLButtonElement | null>(null);
  const moreLabel = t("categories.more");
  const baseEntries = useMemo(
    () => (stats ? buildCategoryFilterEntries(allLabel, stats.total, stats.items, null) : []),
    [allLabel, stats],
  );
  const entries = useMemo(
    () =>
      promotedCategory && stats
        ? buildCategoryFilterEntries(allLabel, stats.total, stats.items, promotedCategory)
        : baseEntries,
    [allLabel, baseEntries, promotedCategory, stats],
  );
  const firstRowEntries = entries.slice(0, layout.firstRowCount);
  const secondRowEntries = entries.slice(
    layout.firstRowCount,
    layout.firstRowCount + layout.secondRowCount,
  );
  const visibleCategoryKeys = [...firstRowEntries, ...secondRowEntries].map((entry) => entry.key);

  useLayoutEffect(() => {
    const measureContainer = measureRef.current;
    const categoryArea = categoryAreaRef.current;
    if (!measureContainer || !categoryArea || entries.length === 0) {
      setLayout({ firstRowCount: 0, secondRowCount: 0, secondRowOffset: 0, showMore: false });
      return;
    }

    let animationFrame: number | null = null;
    const updateLayout = () => {
      const chips = Array.from(
        measureContainer.querySelectorAll<HTMLElement>("[data-category-chip-measure]"),
      );
      const moreChip = measureContainer.querySelector<HTMLElement>("[data-category-more-measure]");
      const width = measureContainer.clientWidth;
      if (chips.length !== entries.length || !moreChip || width <= 0) {
        return;
      }

      const measuredLayout = getCategoryFilterLayout(
        chips.map((chip) => ({ width: chip.offsetWidth })),
        Math.max(0, measureContainer.clientWidth - 24),
        moreChip.offsetWidth + 8,
        6,
      );
      const nextLayout = {
        ...measuredLayout,
        secondRowOffset:
          measuredLayout.secondRowCount > 0 || measuredLayout.showMore
            ? measuredLayout.secondRowOffset + 24
            : 0,
      };
      setLayout((current) =>
        current.firstRowCount === nextLayout.firstRowCount &&
        current.secondRowCount === nextLayout.secondRowCount &&
        current.secondRowOffset === nextLayout.secondRowOffset &&
        current.showMore === nextLayout.showMore
          ? current
          : nextLayout,
      );
    };
    const scheduleMeasurement = () => {
      if (animationFrame !== null) {
        cancelAnimationFrame(animationFrame);
      }
      animationFrame = requestAnimationFrame(() => {
        animationFrame = null;
        updateLayout();
      });
    };

    scheduleMeasurement();
    const observer = new ResizeObserver(scheduleMeasurement);
    observer.observe(categoryArea);
    return () => {
      observer.disconnect();
      if (animationFrame !== null) {
        cancelAnimationFrame(animationFrame);
      }
    };
  }, [activeCategory, entries, moreLabel]);

  useEffect(() => {
    if (dialogOpen) {
      closeButtonRef.current?.focus();
    }
  }, [dialogOpen]);

  const closeDialog = () => {
    setDialogOpen(false);
    requestAnimationFrame(() => moreButtonRef.current?.focus());
  };
  const selectCategoryFromDialog = (category: string | null) => {
    setPromotedCategory(getCategoryPromotion(category, visibleCategoryKeys));
    onCategoryChange(category);
    closeDialog();
  };
  const selectInlineCategory = (category: string | null) => {
    setPromotedCategory(null);
    onCategoryChange(category);
  };
  const renderCategoryButton = (entry: CategoryFilterEntry) => {
    const isActive = entry.key === activeCategory;
    return (
      <button
        key={entry.key ?? "__all"}
        type="button"
        onClick={() => selectInlineCategory(entry.key)}
        aria-current={isActive ? "true" : undefined}
        className={`group inline-flex h-9 max-w-full items-center gap-1.5 rounded-2xl text-[0.8rem] font-medium transition-all active:scale-[0.97] sm:max-w-[10rem] ${
          isActive
            ? "bg-[rgb(var(--shiro-accent-rgb)/0.12)] px-4 text-[rgb(var(--shiro-accent-rgb)/0.95)] shadow-[0_4px_14px_rgb(var(--shiro-accent-rgb)/0.06)]"
            : "px-2 text-foreground/50 hover:-translate-y-px hover:text-foreground/80"
        }`}
      >
        <span className="min-w-0 flex-1 truncate">{entry.label}</span>
        <span
          className={`inline-flex min-w-4 items-center justify-center text-right text-[0.66rem] font-semibold leading-none tabular-nums ${
            isActive
              ? "text-[rgb(var(--shiro-accent-rgb)/0.72)]"
              : "text-foreground/32 group-hover:text-[rgb(var(--shiro-accent-rgb)/0.72)]"
          }`}
        >
          {entry.count}
        </span>
      </button>
    );
  };

  return (
    <div className={`mt-3 ${showSearch ? "grid gap-4 sm:gap-8 sm:mt-6 sm:grid-cols-[10.5rem_minmax(0,1fr)] sm:items-center" : "sm:mt-6"}`}>
      {showSearch ? (
        <label className="group relative block w-full sm:w-[10.5rem] sm:shrink-0">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-foreground/25 transition-colors group-focus-within:text-[rgb(var(--shiro-accent-rgb)/0.72)]" />
          <input
            type="search"
            placeholder={searchPlaceholder}
            value={search}
            onChange={(event) => onSearchChange(event.target.value)}
            maxLength={100}
            aria-label={searchPlaceholder}
            className="w-full rounded-xl border border-foreground/8 bg-foreground/[0.03] py-2.5 pl-10 pr-4 text-sm text-foreground placeholder:text-foreground/25 outline-none transition-colors focus:border-[rgb(var(--shiro-border-rgb)/0.32)] focus:bg-[rgb(var(--shiro-panel-rgb)/0.35)]"
          />
        </label>
      ) : null}

      <div ref={categoryAreaRef} className="relative min-w-0 sm:h-11">
        <div className="sm:absolute sm:inset-x-0 sm:top-1/2 sm:-translate-y-1/2">
          {isLoading ? (
          <span className="inline-flex min-h-10 items-center text-xs text-foreground/30">
            {t("categories.loading")}
          </span>
        ) : errorMessage ? (
          <div className="flex min-h-10 items-center gap-3 text-xs text-foreground/35">
            <span>{t("categories.loadFailed")}</span>
            {onRetry ? (
              <button type="button" onClick={onRetry} className="text-[rgb(var(--shiro-accent-rgb)/0.76)]">
                {t("categories.retry")}
              </button>
            ) : null}
          </div>
          ) : (
            <div className="space-y-2 py-0.5" aria-label={t("categories.dialogTitle")}>
              <div className="flex min-h-9 flex-wrap content-start justify-start gap-1.5 sm:flex-nowrap sm:justify-end">
                {firstRowEntries.map(renderCategoryButton)}
              </div>
              {secondRowEntries.length > 0 || layout.showMore ? (
                <div
                  className="flex min-h-9 flex-wrap content-start justify-start gap-1.5 sm:flex-nowrap sm:ms-[var(--category-second-row-offset)]"
                  style={{ "--category-second-row-offset": `${layout.secondRowOffset}px` } as CSSProperties}
                >
                  {secondRowEntries.map(renderCategoryButton)}
                  {layout.showMore ? (
                    <button
                      ref={moreButtonRef}
                      type="button"
                      onClick={() => setDialogOpen(true)}
                      className="ml-2 inline-flex h-9 items-center text-[0.8rem] font-medium text-foreground/55 underline decoration-foreground/25 underline-offset-4 transition-colors hover:text-[rgb(var(--shiro-accent-rgb)/0.82)] hover:decoration-[rgb(var(--shiro-accent-rgb)/0.48)]"
                    >
                      {moreLabel}
                    </button>
                  ) : null}
                </div>
              ) : null}
            </div>
          )}
        </div>
        <div
          ref={measureRef}
          aria-hidden="true"
          data-category-filter-measure
          className="pointer-events-none invisible absolute inset-x-0 top-0 -z-10"
        >
          <div className="flex flex-wrap gap-1.5">
            {entries.map((entry) => (
              <span
                key={entry.key ?? "__all-measure"}
                data-category-chip-measure
                className={`inline-flex h-9 max-w-full items-center gap-1.5 rounded-2xl text-[0.8rem] font-medium sm:max-w-[10rem] ${
                  entry.key === activeCategory ? "px-4" : "px-2"
                }`}
              >
                <span className="min-w-0 flex-1 truncate">{entry.label}</span>
                <span className="inline-flex min-w-4 items-center justify-center text-[0.66rem] font-semibold leading-none tabular-nums">
                  {entry.count}
                </span>
              </span>
            ))}
            <span
              data-category-more-measure
              className="ml-2 inline-flex h-9 items-center text-[0.8rem] font-medium underline underline-offset-4"
            >
              {moreLabel}
            </span>
          </div>
        </div>
      </div>

      {dialogOpen ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-background/60 p-3 backdrop-blur-sm sm:p-4"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) {
              closeDialog();
            }
          }}
        >
          <div
            role="dialog"
            aria-modal="true"
            aria-label={t("categories.dialogTitle")}
            onKeyDown={(event) => {
              if (event.key === "Escape") {
                event.preventDefault();
                closeDialog();
              }
            }}
            className="liquid-glass flex max-h-[min(78dvh,34rem)] w-[88vw] max-w-[26rem] sm:w-full sm:max-w-xl flex-col overflow-hidden rounded-[1.75rem] border border-[rgb(var(--shiro-border-rgb)/0.24)] p-5 text-foreground shadow-[0_24px_70px_rgba(15,23,42,0.18)] sm:max-h-[min(80dvh,42rem)] sm:p-6"
          >
            <div className="mb-3 flex shrink-0 items-center justify-between gap-4 sm:mb-4">
              <h2 className="text-sm font-semibold tracking-[-0.01em] text-foreground/88">{t("categories.dialogTitle")}</h2>
              <button
                ref={closeButtonRef}
                type="button"
                onClick={closeDialog}
                aria-label={t("common.close")}
                className="rounded-full border border-[rgb(var(--shiro-border-rgb)/0.18)] bg-white/54 p-2 text-foreground/54 transition hover:text-foreground/84 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-[#0A84FF]/25 dark:bg-black/18"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain scrollbar-hide px-0.5 pb-0.5">
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 sm:gap-2.5">
                {baseEntries.map((entry) => {
                  const tintHue = CATEGORY_TINT_HUES[getCategoryColorIndex(entry.label)];
                  const isActive = entry.key === activeCategory;
                  return (
                    <button
                      key={entry.key ?? "__all-dialog"}
                      type="button"
                      onClick={() => selectCategoryFromDialog(entry.key)}
                      style={
                        isActive
                          ? undefined
                          : ({ "--category-tint-hue": tintHue } as CSSProperties)
                      }
                      className={`flex min-h-12 min-w-0 items-center gap-3 rounded-[1rem] border px-3.5 py-2.5 text-left outline-none transition-[transform,background-color,border-color,box-shadow] hover:-translate-y-px active:translate-y-0 active:scale-[0.99] focus-visible:ring-4 focus-visible:ring-[#0A84FF]/25 sm:min-h-14 sm:px-4 sm:py-3.5 ${
                        isActive
                          ? "border-[#007AFF] bg-[#007AFF] text-white shadow-[inset_0_1px_0_rgba(255,255,255,0.32),0_10px_24px_rgba(0,122,255,0.26)]"
                          : "border-[hsl(var(--category-tint-hue)_64%_74%_/_0.62)] bg-[hsl(var(--category-tint-hue)_72%_92%_/_0.44)] text-[hsl(var(--category-tint-hue)_52%_31%)] shadow-[inset_0_1px_0_rgba(255,255,255,0.62)] hover:border-[hsl(var(--category-tint-hue)_68%_66%_/_0.74)] hover:bg-[hsl(var(--category-tint-hue)_76%_89%_/_0.66)] hover:shadow-[0_10px_24px_rgba(15,23,42,0.06)] dark:border-[hsl(var(--category-tint-hue)_62%_72%_/_0.3)] dark:bg-[hsl(var(--category-tint-hue)_68%_65%_/_0.12)] dark:text-[hsl(var(--category-tint-hue)_88%_86%)] dark:hover:border-[hsl(var(--category-tint-hue)_74%_78%_/_0.42)] dark:hover:bg-[hsl(var(--category-tint-hue)_74%_68%_/_0.18)]"
                      }`}
                    >
                      <span className="min-w-0 flex-1 truncate text-sm font-medium">{entry.label}</span>
                      <span
                        className={`text-right tabular-nums text-sm font-semibold ${
                          isActive ? "text-white/80" : "text-current opacity-60"
                        }`}
                      >
                        {entry.count}
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
