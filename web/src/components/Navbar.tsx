"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { ArrowUpRight, LogOut, Menu, X } from "lucide-react";
import ThemeToggle from "./ThemeToggle";
import { getSession, logout } from "@/lib/api";

export default function Navbar() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const [authed, setAuthed] = useState(false);

  useEffect(() => {
    let active = true;
    getSession().then(session => { if (active) setAuthed(Boolean(session)); });
    return () => { active = false; };
  }, []);

  const links = [
    { href: "/explore", label: "Keşfet" },
    { href: "/#nasil-calisir", label: "Nasıl çalışır?" },
    ...(authed ? [
      { href: "/dashboard", label: "Panelim" },
      { href: "/trips", label: "Gezilerim" },
    ] : []),
  ];

  return (
    <nav className="fixed inset-x-0 top-0 z-50 border-b border-border bg-surface/95 backdrop-blur-xl" aria-label="Ana gezinme">
      <div className="mx-auto flex h-[72px] max-w-7xl items-center justify-between gap-6 px-5 sm:px-8">
        <Link href="/" className="flex shrink-0 items-center" aria-label="TripClip ana sayfa">
          <span className="font-display text-xl font-bold tracking-[-0.045em] text-text">tripclip<span className="text-accent-text">.</span></span>
        </Link>

        <div className="hidden items-center gap-7 lg:flex">
          {links.map(({ href, label }) => (
            <Link key={href} href={href} aria-current={pathname === href ? "page" : undefined}
              className={`border-b-2 py-2 text-sm font-medium transition-colors ${pathname === href ? "border-accent text-text" : "border-transparent text-text-secondary hover:text-text"}`}>
              {label}
            </Link>
          ))}
        </div>

        <div className="hidden items-center gap-3 lg:flex">
          <ThemeToggle />
          {authed ? (
            <button onClick={logout} className="flex items-center gap-2 rounded-md px-4 py-2 text-sm font-semibold text-text-secondary hover:bg-surface2 hover:text-text">
              <LogOut className="h-4 w-4" /> Çıkış
            </button>
          ) : (
            <>
              <Link href="/login" className="rounded-md px-3 py-2 text-sm font-semibold text-text hover:bg-surface2">Giriş yap</Link>
              <Link href="/signup" className="flex items-center gap-2 rounded-md bg-accent px-5 py-2.5 text-sm font-semibold text-on-accent transition-colors hover:bg-accent-hover">
                Ücretsiz başla <ArrowUpRight className="h-4 w-4" />
              </Link>
            </>
          )}
        </div>

        <div className="flex items-center gap-2 lg:hidden">
          <ThemeToggle />
          <button type="button" aria-label={open ? "Menüyü kapat" : "Menüyü aç"} aria-expanded={open}
            onClick={() => setOpen(!open)} className="flex h-10 w-10 items-center justify-center rounded-md border border-border bg-surface text-text">
            {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
        </div>
      </div>
      {open && (
        <div className="border-t border-border bg-bg px-5 py-4 lg:hidden">
          <div className="mx-auto flex max-w-7xl flex-col gap-1">
            {links.map(({ href, label }) => (
              <Link key={href} href={href} onClick={() => setOpen(false)} aria-current={pathname === href ? "page" : undefined}
                className="rounded-lg px-4 py-3 text-sm font-semibold text-text hover:bg-surface2">
                {label}
              </Link>
            ))}
            <div className="mt-2 border-t border-border pt-2">
              {authed ? (
                <button onClick={logout} className="flex w-full items-center gap-3 rounded-lg px-4 py-3 text-sm font-semibold text-destructive"><LogOut className="h-4 w-4" /> Çıkış</button>
              ) : (
                <div className="flex gap-2"><Link href="/login" onClick={() => setOpen(false)} className="flex-1 rounded-md border border-border px-4 py-3 text-center text-sm font-semibold">Giriş yap</Link><Link href="/signup" onClick={() => setOpen(false)} className="flex-1 rounded-md bg-accent px-4 py-3 text-center text-sm font-semibold text-on-accent">Kaydol</Link></div>
              )}
            </div>
          </div>
        </div>
      )}
    </nav>
  );
}
