"use client";

import { Moon, Sun } from "lucide-react";
import { useTheme } from "@/lib/theme";

export default function ThemeToggle() {
  const { theme, toggle } = useTheme();
  const isLight = theme === "light";

  return (
    <button
      onClick={toggle}
      aria-label={isLight ? "Karanlık moda geç" : "Aydınlık moda geç"}
      className="relative w-9 h-9 flex items-center justify-center rounded-md bg-white/[0.04] hover:bg-white/[0.08] text-text-secondary hover:text-text transition-all"
      title={isLight ? "Karanlık Mod" : "Aydınlık Mod"}
    >
      <Sun
        className={`w-4 h-4 absolute transition-all ${
          isLight ? "opacity-100 rotate-0 scale-100" : "opacity-0 -rotate-90 scale-50"
        }`}
      />
      <Moon
        className={`w-4 h-4 absolute transition-all ${
          isLight ? "opacity-0 rotate-90 scale-50" : "opacity-100 rotate-0 scale-100"
        }`}
      />
    </button>
  );
}
