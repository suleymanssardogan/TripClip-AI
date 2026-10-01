"use client";

import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";

type Theme = "dark" | "light";

interface ThemeCtx {
  theme: Theme;
  toggle: () => void;
  setTheme: (t: Theme) => void;
}

const Ctx = createContext<ThemeCtx | null>(null);
const STORAGE_KEY = "tripclip-theme";

function applyTheme(t: Theme) {
  if (typeof window === "undefined") return;
  const html = document.documentElement;
  html.classList.toggle("light", t === "light");
  html.classList.toggle("dark", t === "dark");
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<Theme>("light");

  // Initial mount: an explicit saved choice wins; the journal opens in light mode.
  useEffect(() => {
    const saved = localStorage.getItem(STORAGE_KEY) as Theme | null;
    const initial: Theme = saved === "dark" ? "dark" : "light";
    applyTheme(initial);
    setTimeout(() => {
      setThemeState(initial);
    }, 0);
  }, []);

  function setTheme(t: Theme) {
    applyTheme(t);
    setThemeState(t);
    localStorage.setItem(STORAGE_KEY, t);
  }

  function toggle() {
    setTheme(theme === "dark" ? "light" : "dark");
  }

  return <Ctx.Provider value={{ theme, toggle, setTheme }}>{children}</Ctx.Provider>;
}

export function useTheme() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useTheme must be used inside <ThemeProvider>");
  return ctx;
}
