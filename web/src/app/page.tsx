"use client";

import { useEffect, useRef, useState } from "react";
import { motion, useScroll, useTransform } from "framer-motion";
import { ArrowRight, Play, Cpu, MapPin, Mic, Eye, ChevronDown, Sparkles } from "lucide-react";
import Link from "next/link";
import Navbar from "@/components/Navbar";
import { getStats, type PlatformStats } from "@/lib/api";
import { buttonVariants } from "@/components/ui/Button";
import { cn } from "@/lib/utils";

const FEATURES = [
  { icon: Eye,    label: "Görsel Analiz",   desc: "YOLOv8 ve Google Vision ile kareler taranır, nesneler ve simge yapılar tanınır." },
  { icon: Mic,    label: "Ses Analizi",     desc: "Whisper ile konuşma metne çevrilir, yer isimleri konuşmadan da çıkarılır." },
  { icon: Cpu,    label: "Konum Çıkarımı",  desc: "Türkçe BERT tabanlı NER, altyazı ve konuşmadan gerçek yer adlarını ayıklar." },
  { icon: MapPin, label: "Rota Optimizasyonu", desc: "Nominatim ile konumlar eşleşir, TSP algoritması en verimli sırayı bulur." },
];

const TICKER = [
  "Halfeti","Kapadokya","Ölüdeniz","Pamukkale","Efes",
  "Göbeklitepe","Antalya","İstanbul","Mardin","Trabzon","Bodrum",
];

const STEPS = [
  { num: "01", title: "Video Paylaş",  desc: "Bir gezi videosu yükle ya da Instagram/YouTube linkini yapıştır." },
  { num: "02", title: "AI Analiz Eder", desc: "Görüntü, ses ve yazı aynı anda işlenir; konumlar birleştirilip doğrulanır." },
  { num: "03", title: "Plan Hazır",   desc: "Sıralı rota, harita ve seyahat ipuçlarıyla eksiksiz bir gezi planı çıkar." },
];

/** Decorative scenic illustration — sky gradient + hills + balloons. */
function SceneCard({ className = "" }: { className?: string }) {
  return (
    <div className={`relative overflow-hidden rounded-lg ${className}`}
      style={{ background: "linear-gradient(180deg, #12141C, #2B2320)" }}>
      <svg viewBox="0 0 400 320" preserveAspectRatio="xMidYMid slice" className="absolute inset-0 w-full h-full">
        <circle cx="300" cy="90" r="52" fill="#FFC352" />
        <path d="M0 200 Q100 160 200 195 T400 180 V320 H0 Z" fill="#23262E" />
        <path d="M0 240 Q120 215 220 235 T400 225 V320 H0 Z" fill="#181A1F" />
        <g><ellipse cx="120" cy="140" rx="30" ry="38" fill="#FFB020" /><rect x="112" y="174" width="16" height="10" rx="2" fill="#3a2a12" /></g>
        <g><ellipse cx="210" cy="100" rx="22" ry="28" fill="#EDE7DC" /></g>
        <g><ellipse cx="260" cy="170" rx="16" ry="20" fill="#C4573A" /></g>
      </svg>
    </div>
  );
}

export default function LandingPage() {
  const [stats, setStats] = useState<PlatformStats | null>(null);
  const heroRef = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({ target: heroRef });
  const heroY       = useTransform(scrollYProgress, [0, 1], [0, 80]);
  const heroOpacity = useTransform(scrollYProgress, [0, 0.75], [1, 0]);

  useEffect(() => { getStats().then(setStats).catch(() => {}); }, []);

  return (
    <div className="min-h-screen overflow-x-hidden bg-bg">
      <Navbar />

      {/* HERO */}
      <section ref={heroRef} className="relative pt-32 pb-24 px-6 overflow-hidden">
        <div
          aria-hidden
          className="absolute -top-32 -left-32 w-[36rem] h-[36rem] rounded-full opacity-[0.1] blur-3xl pointer-events-none"
          style={{ background: "radial-gradient(circle, rgb(var(--c-accent)) 0%, rgb(var(--c-route)) 70%, transparent 100%)" }}
        />
        <div className="max-w-6xl mx-auto grid lg:grid-cols-[1.1fr_1fr] gap-12 items-center relative">
          <motion.div style={{ y: heroY, opacity: heroOpacity }} className="relative z-10">
            <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}
              className="inline-flex items-center gap-2.5 mb-8 px-4 py-1.5 rounded-full border border-border bg-surface2">
              <span className="glow-dot" />
              <span className="font-mono text-[11px] text-text-secondary tracking-widest uppercase">
                Reel&apos;den Gezi Planına
              </span>
            </motion.div>

            <motion.h1 initial={{ opacity: 0, y: 32 }} animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.7, delay: 0.1 }}
              className="font-display font-black leading-[0.98] tracking-tight mb-6"
              style={{ fontSize: "clamp(2.75rem, 6vw, 4.5rem)" }}>
              <span className="text-text block">İzledin.</span>
              <span className="text-accent-text block">Şimdi git.</span>
            </motion.h1>

            <motion.p initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.25 }}
              className="text-text-secondary text-lg max-w-md mb-10 leading-relaxed">
              Bir gezi videosu paylaş — TripClip AI konumları, rotayı ve tahmini bütçeyi
              çıkarır. Geriye kalan tek şey gitmek.
            </motion.p>

            <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.35 }}
              className="flex flex-col sm:flex-row items-start gap-4">
              <Link href="/login" className={cn(buttonVariants({ size: "lg" }), "group")}>
                Hemen Başla
                <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
              </Link>
              <Link href="/explore" className={buttonVariants({ variant: "outline", size: "lg" })}>
                <Play className="w-4 h-4" /> Gezileri Keşfet
              </Link>
            </motion.div>

            {stats && (
              <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.8 }}
                className="flex items-center gap-10 mt-16 pt-8 border-t border-border">
                {[
                  { val: stats.completed_videos, label: "Video Analiz" },
                  { val: stats.total_cities,     label: "Şehir Tespit" },
                  { val: stats.total_users,      label: "Kullanıcı" },
                ].map((s, i) => (
                  <div key={i}>
                    <p className="font-mono font-semibold text-3xl text-text tabular-nums">{s.val}+</p>
                    <p className="font-mono text-[10px] text-text-tertiary mt-1 tracking-widest uppercase">
                      {s.label}
                    </p>
                  </div>
                ))}
              </motion.div>
            )}
          </motion.div>

          <motion.div initial={{ opacity: 0, scale: 0.96 }} animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.7, delay: 0.2 }}>
            <SceneCard className="h-[380px] shadow-card" />
          </motion.div>
        </div>

        <motion.div animate={{ y: [0, 8, 0] }} transition={{ repeat: Infinity, duration: 2 }}
          className="hidden lg:flex justify-center mt-16 text-text-tertiary">
          <ChevronDown className="w-5 h-5" />
        </motion.div>
      </section>

      {/* TICKER */}
      <div className="relative overflow-hidden border-y border-border py-3">
        <div className="flex gap-14 whitespace-nowrap animate-ticker">
          {[...TICKER, ...TICKER, ...TICKER].map((item, i) => (
            <span key={i} className="text-sm font-mono text-text-tertiary flex items-center gap-4">
              <span className={`w-1 h-1 rounded-full flex-shrink-0 ${i % 2 === 0 ? "bg-route" : "bg-accent"}`} />
              {item}
            </span>
          ))}
        </div>
      </div>

      {/* NASIL ÇALIŞIR */}
      <section className="py-28 px-6 max-w-6xl mx-auto">
        <motion.div initial={{ opacity: 0, y: 24 }} whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }} className="mb-16">
          <p className="font-mono text-xs text-text-tertiary tracking-widest uppercase mb-3">Nasıl Çalışır</p>
          <h2 className="font-display font-black text-3xl md:text-4xl text-text tracking-tight">
            Üç adımda hazır.
          </h2>
        </motion.div>

        <div className="grid md:grid-cols-3 gap-5">
          {STEPS.map((step, i) => (
            <motion.div key={i}
              initial={{ opacity: 0, y: 28 }} whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }} transition={{ delay: i * 0.1 }}
              className="relative rounded-lg p-7 bg-surface border border-border hover:border-border-strong transition-colors">
              <p className="font-mono text-[11px] text-accent-text mb-4 tracking-widest">ADIM {step.num}</p>
              <h3 className="font-display font-bold text-xl text-text mb-3">{step.title}</h3>
              <p className="text-text-secondary text-sm leading-relaxed">{step.desc}</p>
            </motion.div>
          ))}
        </div>
      </section>

      {/* DASHBOARD ÖNİZLEME */}
      <section className="py-20 px-6 max-w-6xl mx-auto">
        <motion.div initial={{ opacity: 0, y: 24 }} whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }} className="mb-12">
          <p className="font-mono text-xs text-text-tertiary tracking-widest uppercase mb-3">Örnek</p>
          <h2 className="font-display font-black text-3xl md:text-4xl text-text tracking-tight">
            Her gezi, tek bir kart.
          </h2>
        </motion.div>

        <motion.div initial={{ opacity: 0, y: 24 }} whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }} transition={{ delay: 0.1 }}
          className="relative max-w-md rounded-lg border border-border bg-surface overflow-hidden shadow-card">
          {/* Kartın kendisi gerçek bir sonuçla birebir aynı stilde olduğu için
              (aynı rozet, aynı düzen) — üstteki bölüm etiketi ("Örnek") yeterli
              değil, kart tek başına paylaşılsa/kopyalansa bile bunun bir mockup
              olduğu net olmalı. */}
          <span className="absolute top-3 left-3 z-10 font-mono text-[9px] px-2 py-1 rounded-full bg-bg/90 backdrop-blur border border-border-strong text-text-tertiary uppercase tracking-widest">
            Örnek Görünüm
          </span>
          <SceneCard className="h-40" />
          <div className="p-5">
            <div className="flex items-center justify-between mb-2">
              <h3 className="font-display font-bold text-lg text-text">Kapadokya, Türkiye</h3>
              <span className="font-mono text-[10px] px-2 py-1 rounded-full bg-route/10 border border-route/25 text-route uppercase tracking-widest">
                Rota Hazır
              </span>
            </div>
            <p className="text-text-tertiary text-xs">3 gün · 7 nokta · 1 video&apos;dan oluşturuldu</p>
          </div>
        </motion.div>
      </section>

      {/* AI MODELLER */}
      <section className="py-20 px-6 max-w-6xl mx-auto">
        <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }} className="mb-12">
          <p className="font-mono text-xs text-text-tertiary tracking-widest uppercase mb-3">Motor</p>
          <h2 className="font-display font-black text-3xl text-text tracking-tight">Videoyu nasıl okuyoruz</h2>
        </motion.div>

        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {FEATURES.map((f, i) => (
            <motion.div key={i}
              initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }} transition={{ delay: i * 0.08 }}
              className="rounded-lg p-6 bg-surface border border-border hover:border-border-strong transition-colors">
              <div className="w-11 h-11 rounded-md flex items-center justify-center mb-5 bg-surface2 border border-border">
                <f.icon className="w-5 h-5 text-text-secondary" />
              </div>
              <h3 className="font-display font-bold text-text mb-2">{f.label}</h3>
              <p className="text-text-tertiary text-xs leading-relaxed">{f.desc}</p>
            </motion.div>
          ))}
        </div>
      </section>

      {/* CTA */}
      <section className="py-20 px-6">
        <motion.div initial={{ opacity: 0, y: 16 }}
          whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }}
          className="max-w-3xl mx-auto rounded-lg border border-border bg-surface px-10 py-16 text-center">
          <div className="inline-flex items-center gap-2 bg-surface2 border border-border rounded-full px-4 py-1.5 mb-6">
            <Sparkles className="w-3.5 h-3.5 text-accent-text" />
            <span className="font-mono text-xs text-text-secondary">Fırat Üniversitesi · 2026</span>
          </div>
          <h2 className="font-display font-black text-3xl md:text-4xl text-text mb-5 tracking-tight leading-tight">
            Bir sonraki gezini<br />izlediğin yerden başlat.
          </h2>
          <p className="text-text-secondary mb-10 max-w-md mx-auto text-sm leading-relaxed">
            Yazılım Mühendisliği bitirme projesi. Mobil uygulamadan analiz et,
            web&apos;den keşfet ve paylaş.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Link href="/login" className={cn(buttonVariants({ size: "lg" }), "group")}>
              Ücretsiz Başla
              <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
            </Link>
            <Link href="/explore" className={buttonVariants({ variant: "outline", size: "lg" })}>
              Gezileri Keşfet
            </Link>
          </div>
        </motion.div>
      </section>

      {/* FOOTER */}
      <footer className="border-t border-border py-10 px-6 mt-4">
        <div className="max-w-6xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
          <Link href="/" className="flex items-center gap-2">
            <div className="w-6 h-6 bg-accent rounded-sm flex items-center justify-center">
              <svg viewBox="0 0 16 16" fill="none" className="w-3 h-3">
                <path d="M8 2L14 6v4l-6 4L2 10V6l6-4z" fill="rgb(var(--c-on-accent))" />
              </svg>
            </div>
            <span className="font-display font-black text-sm text-text">
              Trip<span className="text-accent-text">Clip</span>
              <span className="text-text-tertiary font-normal text-xs ml-1">AI</span>
            </span>
          </Link>
          <p className="text-xs text-text-tertiary text-center">
            © 2026 Süleyman Sardoğan · Fırat Üniversitesi Yazılım Mühendisliği
          </p>
          <div className="flex gap-6 text-xs text-text-secondary">
            <Link href="/explore" className="hover:text-text transition-colors">Keşfet</Link>
            <Link href="/login"   className="hover:text-text transition-colors">Giriş</Link>
            <Link href="/signup"  className="hover:text-text transition-colors">Kaydol</Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
