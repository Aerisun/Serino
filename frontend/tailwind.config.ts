import type { Config } from "tailwindcss";
import typography from "@tailwindcss/typography";

export default {
  darkMode: ["class"],
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  prefix: "",
  theme: {
    container: {
      center: true,
      padding: "2rem",
      screens: {
        "2xl": "1400px",
      },
    },
    extend: {
      fontFamily: {
        heading: ["'Instrument Serif'", "serif"],
        body: ["'Barlow'", "sans-serif"],
      },
      colors: {
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        popover: {
          DEFAULT: "hsl(var(--popover))",
          foreground: "hsl(var(--popover-foreground))",
        },
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
      typography: {
        DEFAULT: {
          css: {
            "--tw-prose-body": "hsl(var(--foreground) / 0.55)",
            "--tw-prose-headings": "hsl(var(--foreground) / 0.9)",
            "--tw-prose-links": "rgb(var(--shiro-accent-rgb) / 0.82)",
            "--tw-prose-bold": "hsl(var(--foreground) / 0.75)",
            "--tw-prose-counters": "hsl(var(--foreground) / 0.4)",
            "--tw-prose-bullets": "rgb(var(--shiro-accent-rgb) / 0.4)",
            "--tw-prose-hr": "rgb(var(--shiro-divider-rgb) / 0.26)",
            "--tw-prose-quotes": "hsl(var(--foreground) / 0.6)",
            "--tw-prose-quote-borders": "rgb(var(--shiro-accent-rgb) / 0.34)",
            "--tw-prose-code": "hsl(var(--foreground) / 0.75)",
            "--tw-prose-pre-code": "hsl(var(--foreground) / 0.75)",
            "--tw-prose-pre-bg": "rgb(var(--shiro-panel-rgb) / 0.42)",
            "--tw-prose-th-borders": "rgb(var(--shiro-border-rgb) / 0.28)",
            "--tw-prose-td-borders": "rgb(var(--shiro-border-rgb) / 0.18)",
            "--tw-prose-captions": "hsl(var(--foreground) / 0.35)",
            "h1, h2, h3, h4": {
              fontFamily: "'Instrument Serif', serif",
              fontStyle: "italic",
            },
            a: {
              textDecoration: "none",
              "&:hover": {
                color: "rgb(var(--shiro-accent-rgb) / 0.92)",
              },
            },
            code: {
              backgroundColor: "rgb(var(--shiro-panel-rgb) / 0.42)",
              borderRadius: "0.25rem",
              padding: "0.15em 0.35em",
              fontWeight: "400",
              "&::before": { content: "none" },
              "&::after": { content: "none" },
            },
          },
        },
        invert: {
          css: {
            "--tw-prose-body": "hsl(var(--foreground) / 0.55)",
            "--tw-prose-headings": "hsl(var(--foreground) / 0.9)",
            "--tw-prose-links": "rgb(var(--shiro-accent-rgb) / 0.82)",
            "--tw-prose-bold": "hsl(var(--foreground) / 0.75)",
            "--tw-prose-counters": "hsl(var(--foreground) / 0.4)",
            "--tw-prose-bullets": "rgb(var(--shiro-accent-rgb) / 0.4)",
            "--tw-prose-hr": "rgb(var(--shiro-divider-rgb) / 0.26)",
            "--tw-prose-quotes": "hsl(var(--foreground) / 0.6)",
            "--tw-prose-quote-borders": "rgb(var(--shiro-accent-rgb) / 0.34)",
            "--tw-prose-code": "hsl(var(--foreground) / 0.75)",
            "--tw-prose-pre-code": "hsl(var(--foreground) / 0.75)",
            "--tw-prose-pre-bg": "rgb(var(--shiro-panel-rgb) / 0.42)",
            "--tw-prose-th-borders": "rgb(var(--shiro-border-rgb) / 0.28)",
            "--tw-prose-td-borders": "rgb(var(--shiro-border-rgb) / 0.18)",
            "--tw-prose-captions": "hsl(var(--foreground) / 0.35)",
            code: {
              backgroundColor: "rgb(var(--shiro-panel-rgb) / 0.42)",
            },
          },
        },
      },
    },
  },
  plugins: [typography],
} satisfies Config;
