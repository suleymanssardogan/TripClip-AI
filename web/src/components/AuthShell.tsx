import Image from "next/image";
import type { ReactNode } from "react";

export default function AuthShell({ children }: { children: ReactNode }) {
  return (
    <main className="grid min-h-screen bg-bg lg:grid-cols-[0.9fr_1.1fr]">
      <aside className="relative hidden min-h-screen overflow-hidden lg:block">
        <Image src="/images/istanbul-editorial.webp" alt="İstanbul kıyısı ve vapurların temsili seyahat görseli" fill sizes="45vw" className="object-cover object-[65%_center]" />
        <div className="absolute inset-0 bg-gradient-to-t from-[#102d45]/85 via-[#102d45]/15 to-transparent" aria-hidden="true" />
        <div className="absolute bottom-12 left-12 right-12 text-white xl:bottom-16 xl:left-16 xl:right-16">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-white/75">TripClip</p>
          <p className="mt-4 max-w-md font-display text-4xl font-bold leading-tight tracking-[-0.055em]">Bir sonraki yolculuğun burada başlar.</p>
          <p className="mt-5 text-xs text-white/70">İstanbul, Türkiye · Temsili görsel</p>
        </div>
      </aside>
      <div className="flex min-h-screen items-center justify-center px-5 py-12 sm:px-8">
        <div className="w-full max-w-md">{children}</div>
      </div>
    </main>
  );
}
