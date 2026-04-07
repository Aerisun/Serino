import { useTheme } from "@serino/theme";
import { useFrontendI18n } from "@/i18n";
import { Monitor, Moon, Sun } from "@/components/icons/AppIcon";

const cycle = ["light", "dark", "system"] as const;
const icons = { light: Sun, dark: Moon, system: Monitor };

interface ThemeToggleProps {
  glassVariant?: "default" | "hero";
}

const ThemeToggle = ({ glassVariant = "default" }: ThemeToggleProps) => {
  const { t } = useFrontendI18n();
  const { theme, setTheme } = useTheme();

  const next = () => {
    const i = cycle.indexOf(theme);
    setTheme(cycle[(i + 1) % cycle.length]);
  };

  const Icon = icons[theme];
  const glassClass = glassVariant === "hero" ? "liquid-glass-hero" : "liquid-glass";
  const toneClass =
    glassVariant === "hero"
      ? "text-white/72 hover:text-white"
      : "text-foreground/60 hover:text-foreground";

  return (
    <button
      type="button"
      onClick={next}
      className={`flex h-9 w-9 items-center justify-center rounded-full ${glassClass} ${toneClass} transition-colors active:scale-95`}
      aria-label={t("common.themeToggle")}
    >
      <Icon className="h-4 w-4" />
    </button>
  );
};

export default ThemeToggle;
