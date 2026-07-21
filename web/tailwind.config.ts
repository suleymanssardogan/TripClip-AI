import type { Config } from "tailwindcss";

const cssVar = (name: string) => `rgb(var(${name}) / <alpha-value>)`;

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // ── Design system tokens (see design-system artifact) ──────────────
        bg:            cssVar("--c-bg"),
        surface:       cssVar("--c-surface"),
        surface2:      cssVar("--c-surface2"),
        border:        cssVar("--c-border"),
        "border-strong": cssVar("--c-border-strong"),
        text:          cssVar("--c-text"),
        "text-secondary": cssVar("--c-text-secondary"),
        "text-tertiary":  cssVar("--c-text-tertiary"),
        accent:        cssVar("--c-accent"),
        "accent-hover": cssVar("--c-accent-hover"),
        "accent-text":  cssVar("--c-accent-text"),
        "on-accent":    cssVar("--c-on-accent"),
        route:         cssVar("--c-route"),
        success:       cssVar("--c-success"),
        warning:       cssVar("--c-warning"),
        destructive:   cssVar("--c-destructive"),
      },
      fontFamily: {
        display: ["var(--font-satoshi)", "sans-serif"],
        sans:    ["var(--font-general-sans)", "sans-serif"],
        mono:    ["var(--font-jbmono)", "ui-monospace", "monospace"],
      },
      borderRadius: {
        xs:  "6px",
        sm:  "10px",
        md:  "14px",
        lg:  "20px",
        xl:  "28px",
        "4xl": "2rem",
        "5xl": "2.5rem",
      },
      animation: {
        "float":       "float 6s ease-in-out infinite",
        "glow-pulse":  "glow-pulse 3s ease-in-out infinite",
        "slide-up":    "slide-up 0.6s cubic-bezier(0.16,1,0.3,1) forwards",
        "fade-in":     "fade-in 0.8s ease forwards",
        "ticker":      "ticker 25s linear infinite",
        "shimmer":     "shimmer 1.4s ease infinite",
        "pulse-ring":  "pulse-ring 1.6s cubic-bezier(0.4,0,0.2,1) infinite",
      },
      keyframes: {
        float: {
          "0%,100%": { transform: "translateY(0px)" },
          "50%":     { transform: "translateY(-12px)" },
        },
        // Decorative glow only — kept as a static dark-mode accent color
        // since @keyframes can't consume CSS custom properties cleanly
        // through Tailwind's config-time string interpolation.
        "glow-pulse": {
          "0%,100%": { boxShadow: "0 0 20px rgba(255,176,32,0.15)" },
          "50%":     { boxShadow: "0 0 40px rgba(255,176,32,0.4), 0 0 80px rgba(255,176,32,0.1)" },
        },
        "slide-up": {
          from: { opacity: "0", transform: "translateY(24px)" },
          to:   { opacity: "1", transform: "translateY(0)" },
        },
        "fade-in": {
          from: { opacity: "0" },
          to:   { opacity: "1" },
        },
        ticker: {
          from: { transform: "translateX(0)" },
          to:   { transform: "translateX(-33.33%)" },
        },
        shimmer: {
          "0%":   { backgroundPosition: "100% 0" },
          "100%": { backgroundPosition: "0 0" },
        },
        "pulse-ring": {
          "0%":   { boxShadow: "0 0 0 0 rgba(255,176,32,0.5)" },
          "70%":  { boxShadow: "0 0 0 8px rgba(255,176,32,0)" },
          "100%": { boxShadow: "0 0 0 0 rgba(255,176,32,0)" },
        },
      },
      boxShadow: {
        card: "0 4px 24px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255,255,255,0.05)",
      },
    },
  },
  plugins: [],
};
export default config;
