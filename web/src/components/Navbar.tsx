"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, useEffect } from "react";
import { LayoutDashboard, Compass, LogOut, Menu, X, Upload } from "lucide-react";
import ThemeToggle from "./ThemeToggle";
import { logout } from "@/lib/api";

export default function Navbar() {
  const pathname = usePathname();
  const [scrolled, setScrolled] = useState(false);
  const [open, setOpen] = useState(false);
  const [authed, setAuthed] = useState(false);

  useEffect(() => {
    const hasToken = typeof window !== "undefined" && !!localStorage.getItem("token");
    setTimeout(() => {
      setAuthed(hasToken);
    }, 0);
    const onScroll = () => setScrolled(window.scrollY > 24);
    window.addEventListener("scroll", onScroll);
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  const links = [
    { href: "/explore",   label: "Keşfet",    icon: Compass },
    ...(authed ? [
      { href: "/upload",    label: "Yükle",     icon: Upload },
      { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
    ] : []),
  ];

  return (
    <nav className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 ${
      scrolled
        ? "bg-bg/85 backdrop-blur-2xl border-b border-border"
        : ""
    }`}>
      <div className="max-w-7xl mx-auto px-6 h-[60px] flex items-center justify-between">

        {/* Logo */}
        <Link href="/" className="flex items-center gap-2.5 group">
          <div className="relative w-8 h-8 flex-shrink-0">
            <div className="absolute inset-0 bg-accent/15 rounded-md group-hover:bg-accent/25 transition-colors" />
            <div className="absolute inset-[3px] bg-accent rounded-sm flex items-center justify-center">
              <svg viewBox="0 0 16 16" fill="none" className="w-3.5 h-3.5">
                <path d="M8 2L14 6v4l-6 4L2 10V6l6-4z" fill="rgb(var(--c-on-accent))" />
                <circle cx="8" cy="8" r="1.8" fill="rgb(var(--c-on-accent))" opacity="0.5" />
              </svg>
            </div>
          </div>
          <span className="font-display font-black text-[17px] tracking-tight text-text">
            Trip<span className="text-accent-text">Clip</span>
          </span>
          <span className="hidden sm:block font-mono text-[9px] text-text-tertiary border border-border-strong px-1.5 py-0.5 rounded-xs">
            AI
          </span>
        </Link>

        {/* Desktop nav */}
        <div className="hidden md:flex items-center gap-1">
          {links.map(({ href, label }) => (
            <Link
              key={href} href={href}
              className={`px-4 py-2 rounded-md text-sm font-medium transition-all ${
                pathname === href
                  ? "bg-accent/8 text-accent-text border border-accent/15"
                  : "text-text-secondary hover:text-text hover:bg-surface2"
              }`}
            >
              {label}
            </Link>
          ))}
        </div>

        {/* Desktop actions */}
        <div className="hidden md:flex items-center gap-3">
          <ThemeToggle />
          {authed ? (
            <button
              onClick={logout}
              className="flex items-center gap-1.5 text-sm text-text-secondary hover:text-destructive transition-colors"
            >
              <LogOut className="w-3.5 h-3.5" /> Çıkış
            </button>
          ) : (
            <>
              <Link href="/login"
                className="text-sm text-text-secondary hover:text-text transition-colors px-3 py-2">
                Giriş Yap
              </Link>
              <Link href="/signup" className="bg-accent text-on-accent hover:bg-accent-hover transition-colors font-semibold px-4 py-2 rounded-md text-sm">
                Kaydol
              </Link>
            </>
          )}
        </div>

        {/* Mobil: Theme + hamburger */}
        <div className="md:hidden flex items-center gap-2">
          <ThemeToggle />
          <button
            className="w-9 h-9 flex items-center justify-center rounded-md bg-surface2 hover:bg-border text-text-secondary hover:text-text transition-all"
            onClick={() => setOpen(!open)}
          >
            {open ? <X className="w-4 h-4" /> : <Menu className="w-4 h-4" />}
          </button>
        </div>
      </div>

      {/* Mobil menü */}
      {open && (
        <div className="md:hidden bg-bg/95 backdrop-blur-2xl border-b border-border px-6 py-4 space-y-1">
          {links.map(({ href, label, icon: Icon }) => (
            <Link
              key={href} href={href} onClick={() => setOpen(false)}
              className="flex items-center gap-3 py-3 px-3 rounded-md text-sm text-text-secondary hover:text-text hover:bg-surface2 transition-all"
            >
              <Icon className="w-4 h-4" /> {label}
            </Link>
          ))}
          <div className="pt-2 border-t border-border">
            {authed
              ? <button onClick={logout}
                  className="flex items-center gap-3 py-3 px-3 w-full text-sm text-destructive hover:bg-destructive/5 rounded-md transition-all">
                  <LogOut className="w-4 h-4" /> Çıkış Yap
                </button>
              : <Link href="/login" onClick={() => setOpen(false)}
                  className="block py-3 px-3 text-sm text-text-secondary hover:text-text rounded-md">
                  Giriş Yap
                </Link>
            }
          </div>
        </div>
      )}
    </nav>
  );
}
