"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState, useEffect } from "react";
import { LayoutDashboard, Compass, LogOut, Menu, X } from "lucide-react";

export default function Navbar() {
  const pathname = usePathname();
  const router = useRouter();
  const [scrolled, setScrolled] = useState(false);
  const [open, setOpen] = useState(false);
  const [authed, setAuthed] = useState(false);

  useEffect(() => {
    setAuthed(!!localStorage.getItem("token"));
    const onScroll = () => setScrolled(window.scrollY > 24);
    window.addEventListener("scroll", onScroll);
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  const logout = () => { localStorage.clear(); router.push("/login"); };

  const links = [
    { href: "/explore",   label: "Keşfet",    icon: Compass },
    ...(authed ? [{ href: "/dashboard", label: "Dashboard", icon: LayoutDashboard }] : []),
  ];

  return (
    <nav className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 ${
      scrolled
        ? "bg-[#080B14]/85 backdrop-blur-2xl border-b border-white/[0.06] shadow-[0_1px_0_rgba(77,255,195,0.04)]"
        : ""
    }`}>
      <div className="max-w-7xl mx-auto px-6 h-[60px] flex items-center justify-between">

        {/* Logo */}
        <Link href="/" className="flex items-center gap-2.5 group">
          <div className="relative w-8 h-8 flex-shrink-0">
            <div className="absolute inset-0 bg-neon/15 rounded-xl group-hover:bg-neon/25 transition-colors" />
            <div className="absolute inset-[3px] bg-neon rounded-lg flex items-center justify-center">
              <svg viewBox="0 0 16 16" fill="none" className="w-3.5 h-3.5">
                <path d="M8 2L14 6v4l-6 4L2 10V6l6-4z" fill="#080B14" />
                <circle cx="8" cy="8" r="1.8" fill="#080B14" opacity="0.5" />
              </svg>
            </div>
          </div>
          <span className="font-display font-black text-[17px] tracking-tight text-ice">
            Trip<span className="text-neon">Clip</span>
          </span>
          <span className="hidden sm:block text-[9px] font-mono text-neon/45 border border-neon/15 px-1.5 py-0.5 rounded-md">
            AI
          </span>
        </Link>

        {/* Desktop nav */}
        <div className="hidden md:flex items-center gap-1">
          {links.map(({ href, label }) => (
            <Link
              key={href} href={href}
              className={`px-4 py-2 rounded-xl text-sm font-medium transition-all ${
                pathname === href
                  ? "bg-neon/8 text-neon border border-neon/15"
                  : "text-muted hover:text-ice hover:bg-white/[0.05]"
              }`}
            >
              {label}
            </Link>
          ))}
        </div>

        {/* Desktop actions */}
        <div className="hidden md:flex items-center gap-3">
          {authed ? (
            <button
              onClick={logout}
              className="flex items-center gap-1.5 text-sm text-muted hover:text-coral transition-colors"
            >
              <LogOut className="w-3.5 h-3.5" /> Çıkış
            </button>
          ) : (
            <>
              <Link href="/login"
                className="text-sm text-muted hover:text-ice transition-colors px-3 py-2">
                Giriş Yap
              </Link>
              <Link href="/signup" className="btn-primary px-4 py-2 rounded-xl text-sm">
                Kaydol
              </Link>
            </>
          )}
        </div>

        {/* Mobil hamburger */}
        <button
          className="md:hidden w-9 h-9 flex items-center justify-center rounded-xl bg-white/[0.04] hover:bg-white/[0.08] text-muted hover:text-ice transition-all"
          onClick={() => setOpen(!open)}
        >
          {open ? <X className="w-4 h-4" /> : <Menu className="w-4 h-4" />}
        </button>
      </div>

      {/* Mobil menü */}
      {open && (
        <div className="md:hidden bg-[#080B14]/95 backdrop-blur-2xl border-b border-white/[0.06] px-6 py-4 space-y-1">
          {links.map(({ href, label, icon: Icon }) => (
            <Link
              key={href} href={href} onClick={() => setOpen(false)}
              className="flex items-center gap-3 py-3 px-3 rounded-xl text-sm text-muted hover:text-ice hover:bg-white/[0.05] transition-all"
            >
              <Icon className="w-4 h-4" /> {label}
            </Link>
          ))}
          <div className="pt-2 border-t border-white/[0.06]">
            {authed
              ? <button onClick={logout}
                  className="flex items-center gap-3 py-3 px-3 w-full text-sm text-coral hover:bg-coral/5 rounded-xl transition-all">
                  <LogOut className="w-4 h-4" /> Çıkış Yap
                </button>
              : <Link href="/login" onClick={() => setOpen(false)}
                  className="block py-3 px-3 text-sm text-muted hover:text-ice rounded-xl">
                  Giriş Yap
                </Link>
            }
          </div>
        </div>
      )}
    </nav>
  );
}
