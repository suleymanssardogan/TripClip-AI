"use client";

import React from "react";
import Link from "next/link";
import { Bell, Map, Clapperboard, CalendarDays, Share2, Compass } from "lucide-react";
import { usePathname } from "next/navigation";

export default function Navbar() {
  const pathname = usePathname();

  const navLinks = [
    { name: "Explore", href: "/explore", icon: Compass },
    { name: "Parser", href: "/", icon: Clapperboard }, // Home is the parser
    { name: "Editor", href: "/editor/default", icon: CalendarDays },
    { name: "Share", href: "/share/default", icon: Share2 },
  ];

  return (
    <header className="fixed top-0 z-[5000] w-full bg-surface/70 backdrop-blur-xl border-b border-white/5">
      <div className="flex justify-between items-center w-full px-6 py-4 max-w-screen-2xl mx-auto">
        {/* Logo & Profile */}
        <div className="flex items-center gap-4">
          <Link href="/dashboard" className="w-10 h-10 rounded-full overflow-hidden border-2 border-primary/20 hover:scale-105 transition-transform">
            <img 
              alt="Profile" 
              className="w-full h-full object-cover" 
              src="https://images.unsplash.com/photo-1539571696357-5a69c17a67c6?auto=format&fit=crop&q=80&w=100" 
            />
          </Link>
          <Link href="/" className="text-2xl font-black text-on-surface tracking-tighter font-headline">
            TripClip AI
          </Link>
        </div>

        {/* Navigation */}
        <nav className="hidden md:flex items-center gap-2">
          {navLinks.map((link) => {
            const isActive = pathname === link.href;
            return (
              <Link 
                key={link.name} 
                href={link.href}
                className={`px-4 py-2 rounded-xl text-sm font-bold font-headline transition-all flex items-center gap-2 ${
                  isActive 
                    ? 'bg-secondary/10 text-secondary' 
                    : 'text-on-surface-variant hover:bg-white/5 hover:text-on-surface'
                }`}
              >
                {link.name}
              </Link>
            );
          })}
        </nav>

        {/* Actions */}
        <div className="flex items-center gap-2">
          <button className="w-10 h-10 flex items-center justify-center rounded-full hover:bg-white/5 transition-colors group">
            <Bell className="w-5 h-5 text-on-surface-variant group-hover:text-primary" />
          </button>
        </div>
      </div>
    </header>
  );
}
