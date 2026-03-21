import { Sun, Moon, Monitor } from "lucide-react";
import { useTheme } from "@/contexts/useTheme";

const cycle = ["light", "dark", "system"] as const;
const icons = { light: Sun, dark: Moon, system: Monitor };

const ThemeToggle = () => {
  const { theme, setTheme } = useTheme();

  const next = () => {
    const i = cycle.indexOf(theme);
    setTheme(cycle[(i + 1) % cycle.length]);
  };

  const Icon = icons[theme];

  return (
    <button
      onClick={next}
      className="flex h-9 w-9 items-center justify-center rounded-full liquid-glass text-foreground/60 hover:text-foreground transition-colors active:scale-95"
      aria-label="切换主题"
    >
      <Icon className="h-4 w-4" />
    </button>
  );
};

export default ThemeToggle;
