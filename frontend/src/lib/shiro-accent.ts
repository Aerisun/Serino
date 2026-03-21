export type ShiroThemeMode = "light" | "dark";

export interface ShiroAccentPalette {
  id: string;
  name: string;
  light: string;
  dark: string;
}

type RgbTuple = [number, number, number];

const LIGHT_BASE: RgbTuple = [245, 247, 250];
const DARK_BASE: RgbTuple = [10, 10, 13];
const LIGHT_SURFACE: RgbTuple = [255, 255, 255];
const DARK_SURFACE: RgbTuple = [20, 22, 29];
const WHITE: RgbTuple = [255, 255, 255];

// Extracted from temp/shiro-full/src/components/modules/shared/AccentColorStyleInjector.tsx
export const SHIRO_ACCENT_PALETTES: ShiroAccentPalette[] = [
  { id: "asagi-momo", name: "浅葱 / 桃", light: "#33A6B8", dark: "#F596AA" },
  { id: "coral-wisteria", name: "珊瑚 / 藤紫", light: "#FF6666", dark: "#A0A7D4" },
  { id: "jade-coral", name: "翡翠 / 珊瑚", light: "#26A69A", dark: "#ff7b7b" },
  { id: "rose-mint", name: "蔷薇 / 薄荷", light: "#fb7287", dark: "#99D8CF" },
  { id: "mist-iris", name: "雾蓝 / 鸢尾", light: "#69a6cc", dark: "#838BC6" },
];

const clampChannel = (value: number) => Math.max(0, Math.min(255, Math.round(value)));

const hexToRgb = (hex: string): RgbTuple => {
  const normalized = hex.replace("#", "");
  const value =
    normalized.length === 3
      ? normalized
          .split("")
          .map((char) => `${char}${char}`)
          .join("")
      : normalized;

  return [
    Number.parseInt(value.slice(0, 2), 16),
    Number.parseInt(value.slice(2, 4), 16),
    Number.parseInt(value.slice(4, 6), 16),
  ];
};

const mixRgb = (base: RgbTuple, tint: RgbTuple, weight: number): RgbTuple => [
  clampChannel(base[0] * (1 - weight) + tint[0] * weight),
  clampChannel(base[1] * (1 - weight) + tint[1] * weight),
  clampChannel(base[2] * (1 - weight) + tint[2] * weight),
];

const rgbToChannels = (rgb: RgbTuple) => rgb.join(" ");

const rgbToHslTriplet = ([red, green, blue]: RgbTuple) => {
  const r = red / 255;
  const g = green / 255;
  const b = blue / 255;
  const max = Math.max(r, g, b);
  const min = Math.min(r, g, b);
  const delta = max - min;

  let hue = 0;
  if (delta !== 0) {
    if (max === r) {
      hue = ((g - b) / delta) % 6;
    } else if (max === g) {
      hue = (b - r) / delta + 2;
    } else {
      hue = (r - g) / delta + 4;
    }
  }

  hue = Math.round(hue * 60);
  if (hue < 0) hue += 360;

  const lightness = (max + min) / 2;
  const saturation =
    delta === 0 ? 0 : delta / (1 - Math.abs(2 * lightness - 1));

  return `${hue} ${Math.round(saturation * 100)}% ${Math.round(lightness * 100)}%`;
};

export const buildShiroAccentTokens = (
  palette: ShiroAccentPalette,
  theme: ShiroThemeMode,
): Record<string, string> => {
  const accentRgb = hexToRgb(theme === "dark" ? palette.dark : palette.light);
  const base = theme === "dark" ? DARK_BASE : LIGHT_BASE;
  const surface = theme === "dark" ? DARK_SURFACE : LIGHT_SURFACE;

  const borderRgb = mixRgb(base, accentRgb, theme === "dark" ? 0.42 : 0.22);
  const inputRgb = mixRgb(base, accentRgb, theme === "dark" ? 0.54 : 0.28);
  const dividerRgb = mixRgb(base, accentRgb, theme === "dark" ? 0.64 : 0.34);
  const panelRgb = mixRgb(surface, accentRgb, theme === "dark" ? 0.14 : 0.08);
  const panelStrongRgb = mixRgb(surface, accentRgb, theme === "dark" ? 0.22 : 0.14);
  const glowRgb = mixRgb(accentRgb, WHITE, theme === "dark" ? 0.08 : 0.18);
  const sheenRgb = mixRgb(WHITE, accentRgb, theme === "dark" ? 0.08 : 0.26);
  const coinBorderRgb = mixRgb(base, accentRgb, theme === "dark" ? 0.82 : 0.56);
  const borderStrongRgb = mixRgb(base, accentRgb, theme === "dark" ? 0.76 : 0.48);

  return {
    "--shiro-accent-rgb": rgbToChannels(accentRgb),
    "--shiro-accent-hsl": rgbToHslTriplet(accentRgb),
    "--shiro-border-rgb": rgbToChannels(borderRgb),
    "--shiro-border-strong-rgb": rgbToChannels(borderStrongRgb),
    "--shiro-divider-rgb": rgbToChannels(dividerRgb),
    "--shiro-panel-rgb": rgbToChannels(panelRgb),
    "--shiro-panel-strong-rgb": rgbToChannels(panelStrongRgb),
    "--shiro-glow-rgb": rgbToChannels(glowRgb),
    "--shiro-sheen-rgb": rgbToChannels(sheenRgb),
    "--shiro-coin-border-rgb": rgbToChannels(coinBorderRgb),
    "--border": rgbToHslTriplet(borderRgb),
    "--input": rgbToHslTriplet(inputRgb),
    "--ring": rgbToHslTriplet(accentRgb),
  };
};
