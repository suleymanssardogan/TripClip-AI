"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState, useEffect } from "react";
import { Map, LayoutDashboard, LogOut, Menu, X } from "lucide-react";

export default function Navbar() {
  const pathname = usePathname();
  const router = useRouter();
  const [scrolled, setScrolled] = useState(false);
  const [open, setOpen] = useState(false);
  const [authed, setAuthed] = useState(false);

  useEffect(() => {
    setAuthed(!!localStorage.getItem("token"));
    const onScroll = () => setScrolled(window.scrollY > 20);
    window.addEventListener("scroll", onScroll);
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  const logout = () => { localStorage.clear(); router.push("/login"); };

  const links = [
    { href: "/explore", label: "Keşfet", icon: Map },
    ...(authed ? [{ href: "/dashboard", label: "Dashboard", icon: LayoutDashboard }] : []),
  ];

  return (
    <nav className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 ${
      scrolled ? "bg-[#080B14]/90 backdrop-blur-xl border-b border-white/5 shadow-lg shadow-black/20" : ""
    }`}>
      <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
        {/* Logo */}
        <Link href="/" className="flex items-center gap-2.5 group">
          <div className="relative w-8 h-8 flex-shrink-0">
            <div className="absolute inset-0 bg-neon/20 rounded-lg group-hover:bg-neon/30 transition-colors" />
            <div className="absolute inset-[3px] bg-neon rounded-md flex items-center justify-center">
              <svg viewBox="0 0 16 16" fill="none" className="w-4 h-4">
                <path d="M8 2L14 6v4l-6 4L2 10V6l6-4z" fill="#080B14" />
                <circle cx="8" cy="8" r="2" fill="#080B14" opacity="0.6" />
              </svg>
            </div>
          </div>
          <span className="font-display font-black text-lg tracking-tight text-ice">
            Trip<span className="text-neon">Clip</span>
          </span>
          <span className="hidden sm:block text-[10px] font-mono text-neon/50 border border-neon/20 px-1.5 py-0.5 rounded">AI</span>
        </Link>

        {/* Desktop */}
        <div className="hidden md:flex items-center gap-1">
          {links.map(({ href, label }) => (
            <Link key={href} href={href} className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
              pathname === href
                ? "bg-neon/10 text-neon border border-neon/20"
                : "text-muted hover:text-ice hover:bg-white/5"
            }`}>{label}</Link>
          ))}
        </div>

        <div className="hidden md:flex items-center gap-3">
          {authed ? (
            <button onClick={logout} className="flex items-center gap-2 text-sm text-muted hover:text-coral transition-colors">
              <LogOut className="w-4 h-4" /> Çıkış
            </button>
          ) : (
            <>
              <Link href="/login" className="text-sm text-muted hover:text-ice transition-colors px-3 py-2">Giriş Yap</Link>
              <Link href="/signup" className="btn-primary px-4 py-2 rounded-lg text-sm">Kaydol</Link>
            </>
          )}
        </div>

        <button className="md:hidden text-muted hover:text-ice" onClick={() => setOpen(!open)}>
          {open ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
        </button>
      </div>

      {open && (
        <div className="md:hidden bg-[#0D1117]/95 backdrop-blur-xl border-b border-white/5 px-6 py-4 space-y-2">
          {links.map(({ href, label, icon: Icon }) => (
            <Link key={href} href={href} onClick={() => setOpen(false)}
              className="flex items-center gap-3 py-2.5 text-sm text-muted hover:text-ice">
              <Icon className="w-4 h-4" /> {label}
            </Link>
          ))}
          {authed
            ? <button onClick={logout} className="flex items-center gap-3 py-2.5 text-sm text-coral"><LogOut className="w-4 h-4" /> Çıkış Yap</button>
            : <Link href="/login" onClick={() => setOpen(false)} className="block py-2.5 text-sm text-muted hover:text-ice">Giriş Yap</Link>
          }
        </div>
      )}
    </nav>
  );
}
