import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        bg:        "#080B14",
        surface:   "#0D1117",
        card:      "#0F1521",
        border:    "#1E2D40",
        neon:      "#4DFFC3",
        violet:    "#8B5CF6",
        coral:     "#FF6B4A",
        ice:       "#E2F0FF",
        muted:     "#4A5568",
        dim:       "#1A2535",
        gold:      "#F5C842",
        "bento-orange": "#2A1205",
        "bento-navy":   "#080B2A",
        "bento-green":  "#091A12",
        "bento-purple": "#130A28",
      },
      fontFamily: {
        display:  ["var(--font-jakarta)", "sans-serif"],
        serif:    ["var(--font-playfair)", "Georgia", "serif"],
        sans:     ["var(--font-inter)", "sans-serif"],
      },
      borderRadius: {
        "4xl": "2rem",
        "5xl": "2.5rem",
      },
      animation: {
        "float":       "float 6s ease-in-out infinite",
        "glow-pulse":  "glow-pulse 3s ease-in-out infinite",
        "slide-up":    "slide-up 0.6s cubic-bezier(0.16,1,0.3,1) forwards",
        "fade-in":     "fade-in 0.8s ease forwards",
        "ticker":      "ticker 25s linear infinite",
      },
      keyframes: {
        float: {
          "0%,100%": { transform: "translateY(0px)" },
          "50%":     { transform: "translateY(-12px)" },
        },
        "glow-pulse": {
          "0%,100%": { boxShadow: "0 0 20px rgba(77,255,195,0.15)" },
          "50%":     { boxShadow: "0 0 40px rgba(77,255,195,0.4), 0 0 80px rgba(77,255,195,0.1)" },
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
      },
      boxShadow: {
        "neon":    "0 0 30px rgba(77,255,195,0.3)",
        "violet":  "0 0 30px rgba(139,92,246,0.3)",
        "coral":   "0 0 30px rgba(255,107,74,0.3)",
        "gold":    "0 0 30px rgba(245,200,66,0.3)",
        "card":    "0 4px 24px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255,255,255,0.05)",
      },
    },
  },
  plugins: [],
};
export default config;
