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
        // High Contrast Palette
        "primary-fixed-dim": "#b2dfdb", // Brighter teal
        "outline": "#8e9b9a",
        "surface-tint": "#2a6865",
        "background": "#0a1416", 
        "on-background": "#f1fafa", // Almost white
        "on-surface": "#f1fafa",    // Almost white for readability
        "surface": "#0a1416",
        "secondary": "#ff8a65",     // Brighter, more vibrant orange
        "primary": "#4db6ac",       // Lighter, readable teal for headers
        "on-primary": "#00201f",
        "surface-container-low": "#142123",
        "surface-container-high": "#1d2e31",
        "surface-container-highest": "#283d41",
        "on-surface-variant": "#c4d1d0", // Light grey for descriptions
        "surface-container-lowest": "#0a1011",
      },
      fontFamily: {
        headline: ["var(--font-jakarta)", "sans-serif"],
        body: ["var(--font-inter)", "sans-serif"],
      },
    },
  },
  plugins: [],
};
export default config;
