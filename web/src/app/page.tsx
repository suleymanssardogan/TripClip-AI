"use client";

import { useEffect, useRef, useState } from "react";
import { motion, useScroll, useTransform } from "framer-motion";
import { ArrowRight, Play, Cpu, MapPin, Mic, Eye, ChevronDown, Sparkles } from "lucide-react";
import Link from "next/link";
import Navbar from "@/components/Navbar";
import { getStats, type PlatformStats } from "@/lib/api";

const FEATURES = [
  { icon: Eye,    label: "Computer Vision", desc: "YOLOv8 + Google Vision ile nesne ve landmark tespiti", color: "#4DFFC3" },
  { icon: Mic,    label: "Ses Analizi",     desc: "Whisper ile Türkçe transkripsiyon ve anahtar kelime tespiti", color: "#8B5CF6" },
  { icon: Cpu,    label: "NER Pipeline",    desc: "Turkish BERT ile lokasyon entity çıkarımı", color: "#FF6B4A" },
  { icon: MapPin, label: "Rota Optimizasyonu", desc: "OpenStreetMap geocoding ve TSP algoritması ile optimum güzergah", color: "#F5C842" },
];

const TICKER = [
  "Halfeti","Kapadokya","Ölüdeniz","Pamukkale","Efes",
  "Göbeklitepe","Antalya","İstanbul","Mardin","Trabzon","Bodrum",
];

const STEPS = [
  { num: "01", title: "Video Yükle",  desc: "Mobil uygulamadan gezi videonu yükle. MP4 / MOV, max 100 MB.",           color: "#4DFFC3" },
  { num: "02", title: "AI Pipeline",  desc: "YOLOv8 → EasyOCR → Whisper → BERT NER → Nominatim → RAG.",              color: "#8B5CF6" },
  { num: "03", title: "Plan Hazır",   desc: "İnteraktif harita, optimize rota, seyahat ipuçları ve paylaşım linki.", color: "#FF6B4A" },
];

const BENTO_PREVIEW = [
  { bg: "#1E0E04", border: "#FF6B4A", label: "Analiz: 24", sub: "tamamlanan",   icon: "📈" },
  { bg: "#06082A", border: "#8B5CF6", label: "Gezi Planım", sub: "AI Powered", icon: "🗺️", large: true },
  { bg: "#F5C842", border: "#F5C842", label: "10₺'den",    sub: "iOS · Ücretsiz", icon: "✈️", light: true },
  { bg: "#06120B", border: "#4DFFC3", label: "48 mekan",   sub: "tespit edildi", icon: "📍" },
];

export default function LandingPage() {
  const [stats, setStats] = useState<PlatformStats | null>(null);
  const heroRef = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({ target: heroRef });
  const heroY       = useTransform(scrollYProgress, [0, 1], [0, 80]);
  const heroOpacity = useTransform(scrollYProgress, [0, 0.75], [1, 0]);

  useEffect(() => { getStats().then(setStats).catch(() => {}); }, []);

  return (
    <div className="min-h-screen overflow-x-hidden">
      <Navbar />

      {/* HERO */}
      <section ref={heroRef}
        className="relative pt-32 pb-40 px-6 overflow-hidden flex flex-col items-center justify-center">
        <div className="absolute inset-0 pointer-events-none">
          <div className="orb w-[600px] h-[600px] bg-neon -top-28 -left-40" style={{opacity:0.07}} />
          <div className="orb w-[500px] h-[500px] bg-violet top-40 -right-32" style={{opacity:0.09}} />
          <div className="orb w-[350px] h-[350px] bg-coral -bottom-10 left-1/3" style={{opacity:0.05}} />
        </div>

        <motion.div style={{ y: heroY, opacity: heroOpacity }}
          className="relative z-10 text-center px-4 max-w-5xl mx-auto">

          <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}
            className="inline-flex items-center gap-2.5 mb-10 px-5 py-2 rounded-full
              border border-neon/20 bg-neon/[0.05]">
            <div className="glow-dot" />
            <span className="text-xs font-mono text-neon/80 tracking-widest uppercase">
              AI-Powered Travel Intelligence
            </span>
          </motion.div>

          <motion.h1 initial={{ opacity: 0, y: 32 }} animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, delay: 0.1 }}
            className="font-serif font-black leading-[0.93] tracking-tight mb-8"
            style={{ fontSize: "clamp(3rem, 10vw, 8rem)" }}>
            <span className="text-ice block">Videodan</span>
            <span className="gradient-text block">Gezi Planına</span>
            <span className="text-ice block">Saniyeler İçinde.</span>
          </motion.h1>

          <motion.p initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.25 }}
            className="text-muted text-lg max-w-md mx-auto mb-10 leading-relaxed">
            Gezi videolarını yükle — AI otomatik olarak OCR, Whisper ve NER
            ile lokasyonları çıkarır, haritalar ve optimize eder.
          </motion.p>

          <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.35 }}
            className="flex flex-col sm:flex-row items-center justify-center gap-4">
            <Link href="/login"
              className="btn-primary px-8 py-4 rounded-2xl text-base font-bold
                flex items-center gap-2 group shadow-[0_0_40px_rgba(77,255,195,0.2)]">
              Hemen Başla
              <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
            </Link>
            <Link href="/explore"
              className="btn-neon px-8 py-4 rounded-2xl text-base font-bold flex items-center gap-2">
              <Play className="w-4 h-4" /> Gezileri Keşfet
            </Link>
          </motion.div>

          {stats && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.8 }}
              className="flex items-center justify-center gap-10 md:gap-20 mt-24 pt-10
                border-t border-white/[0.05]">
              {[
                { val: stats.completed_videos, label: "Video Analiz" },
                { val: stats.total_cities,     label: "Şehir Tespit" },
                { val: stats.total_users,      label: "Kullanıcı" },
              ].map((s, i) => (
                <div key={i} className="text-center">
                  <p className="font-display font-black text-4xl text-neon">{s.val}+</p>
                  <p className="text-[11px] text-muted mt-1.5 tracking-widest uppercase font-mono">
                    {s.label}
                  </p>
                </div>
              ))}
            </motion.div>
          )}
        </motion.div>

        <motion.div animate={{ y: [0, 8, 0] }} transition={{ repeat: Infinity, duration: 2 }}
          className="absolute bottom-10 left-1/2 -translate-x-1/2 text-muted/25">
          <ChevronDown className="w-5 h-5" />
        </motion.div>
      </section>

      {/* TICKER */}
      <div className="relative overflow-hidden border-y border-neon/[0.08] bg-neon/[0.015] py-3">
        <div className="flex gap-14 whitespace-nowrap animate-ticker">
          {[...TICKER, ...TICKER, ...TICKER].map((item, i) => (
            <span key={i} className="text-sm font-mono text-neon/25 flex items-center gap-4">
              <span className="w-1 h-1 rounded-full bg-neon/25 flex-shrink-0" />
              {item}
            </span>
          ))}
        </div>
      </div>

      {/* BENTO PREVIEW */}
      <section className="py-28 px-6 max-w-7xl mx-auto">
        <motion.div initial={{ opacity: 0, y: 24 }} whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }} className="text-center mb-14">
          <p className="text-xs font-mono text-neon/40 tracking-widest uppercase mb-3">Dashboard</p>
          <h2 className="font-serif font-black text-4xl md:text-5xl text-ice tracking-tight">
            Kişisel Gezi <span className="gradient-text-neon">Dashboard'ın</span>
          </h2>
        </motion.div>

        <motion.div initial={{ opacity: 0, y: 32 }} whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }} transition={{ delay: 0.1 }}
          className="grid grid-cols-2 md:grid-cols-4 gap-3 max-w-3xl mx-auto">
          {BENTO_PREVIEW.map((cell, i) => (
            <motion.div key={i}
              initial={{ opacity: 0, scale: 0.92 }}
              whileInView={{ opacity: 1, scale: 1 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.08 + 0.2 }}
              className={`rounded-3xl p-5 flex flex-col gap-2 ${cell.large ? "md:row-span-2" : ""}`}
              style={{ background: cell.bg, border: `1px solid ${cell.border}22` }}>
              <div className="text-3xl">{cell.icon}</div>
              <p className={`font-serif font-black text-xl leading-none ${cell.light ? "text-[#080B14]" : "text-ice"}`}>
                {cell.label}
              </p>
              <p className={`text-xs ${cell.light ? "text-[#080B14]/60" : "text-muted"}`}>
                {cell.sub}
              </p>
            </motion.div>
          ))}
        </motion.div>
      </section>

      {/* NASIL ÇALIŞIR */}
      <section className="py-28 px-6 max-w-7xl mx-auto">
        <motion.div initial={{ opacity: 0, y: 24 }} whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }} className="text-center mb-16">
          <p className="text-xs font-mono text-neon/40 tracking-widest uppercase mb-3">Pipeline</p>
          <h2 className="font-serif font-black text-4xl md:text-5xl text-ice tracking-tight">
            Nasıl Çalışır?
          </h2>
        </motion.div>

        <div className="grid md:grid-cols-3 gap-5">
          {STEPS.map((step, i) => (
            <motion.div key={i}
              initial={{ opacity: 0, y: 28 }} whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }} transition={{ delay: i * 0.12 }}
              className="relative rounded-3xl p-7 overflow-hidden
                bg-white/[0.03] border border-white/[0.07]
                hover:border-white/15 transition-all duration-300">
              <div className="absolute -top-4 -right-2 font-display font-black text-[7rem]
                leading-none select-none pointer-events-none"
                style={{ color: step.color, opacity: 0.05 }}>
                {step.num}
              </div>
              <div className="absolute top-6 right-6 w-2 h-2 rounded-full"
                style={{ background: step.color, boxShadow: `0 0 10px ${step.color}` }} />
              <div className="relative z-10">
                <p className="font-mono text-[11px] mb-4 tracking-widest"
                  style={{ color: step.color }}>ADIM {step.num}</p>
                <h3 className="font-display font-bold text-xl text-ice mb-3">{step.title}</h3>
                <p className="text-muted text-sm leading-relaxed">{step.desc}</p>
              </div>
            </motion.div>
          ))}
        </div>
      </section>

      {/* AI MODELLER */}
      <section className="py-20 px-6 max-w-7xl mx-auto">
        <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }} className="text-center mb-12">
          <p className="text-xs font-mono text-violet/40 tracking-widest uppercase mb-3">Tech Stack</p>
          <h2 className="font-serif font-black text-4xl text-ice tracking-tight">AI Modeller</h2>
        </motion.div>

        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {FEATURES.map((f, i) => (
            <motion.div key={i}
              initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }} transition={{ delay: i * 0.08 }}
              className="rounded-3xl p-6 bg-white/[0.025] border border-white/[0.06]
                hover:border-white/12 transition-all duration-300">
              <div className="w-11 h-11 rounded-2xl flex items-center justify-center mb-5"
                style={{ background: `${f.color}10`, border: `1px solid ${f.color}22` }}>
                <f.icon className="w-5 h-5" style={{ color: f.color }} />
              </div>
              <h3 className="font-display font-bold text-ice mb-2">{f.label}</h3>
              <p className="text-muted text-xs leading-relaxed">{f.desc}</p>
            </motion.div>
          ))}
        </div>
      </section>

      {/* CTA */}
      <section className="py-20 px-6">
        <motion.div initial={{ opacity: 0, scale: 0.97 }}
          whileInView={{ opacity: 1, scale: 1 }} viewport={{ once: true }}
          className="animated-border max-w-4xl mx-auto">
          <div className="bg-[#080B14] rounded-[calc(1.5rem-1px)] px-10 py-16 text-center relative overflow-hidden">
            <div className="absolute inset-0 pointer-events-none">
              <div className="orb w-64 h-64 bg-neon top-0 left-0" style={{opacity:0.06}} />
              <div className="orb w-48 h-48 bg-violet bottom-0 right-0" style={{opacity:0.07}} />
            </div>
            <div className="relative z-10">
              <div className="inline-flex items-center gap-2 bg-neon/8 border border-neon/20
                rounded-full px-4 py-1.5 mb-6">
                <Sparkles className="w-3.5 h-3.5 text-neon" />
                <span className="text-xs font-mono text-neon/80">Fırat Üniversitesi · 2026</span>
              </div>
              <h2 className="font-serif font-black text-4xl md:text-5xl text-ice mb-5
                tracking-tight leading-tight">
                Gezi videolarını<br />
                <span className="gradient-text-neon">akıllı planlara</span> dönüştür.
              </h2>
              <p className="text-muted mb-10 max-w-md mx-auto text-sm leading-relaxed">
                Yazılım Mühendisliği bitirme projesi. Mobil uygulamadan analiz et,
                web'den keşfet ve paylaş.
              </p>
              <div className="flex flex-col sm:flex-row gap-4 justify-center">
                <Link href="/login"
                  className="btn-primary px-8 py-4 rounded-2xl font-bold
                    flex items-center justify-center gap-2 group">
                  Ücretsiz Başla
                  <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
                </Link>
                <Link href="/explore"
                  className="btn-neon px-8 py-4 rounded-2xl font-bold flex items-center justify-center gap-2">
                  Gezileri Keşfet
                </Link>
              </div>
            </div>
          </div>
        </motion.div>
      </section>

      {/* FOOTER */}
      <footer className="border-t border-white/[0.05] py-10 px-6 mt-4">
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
          <Link href="/" className="flex items-center gap-2">
            <div className="w-6 h-6 bg-neon rounded-md flex items-center justify-center">
              <svg viewBox="0 0 16 16" fill="none" className="w-3 h-3">
                <path d="M8 2L14 6v4l-6 4L2 10V6l6-4z" fill="#080B14"/>
              </svg>
            </div>
            <span className="font-display font-black text-sm text-ice">
              Trip<span className="text-neon">Clip</span>
              <span className="text-muted font-normal text-xs ml-1">AI</span>
            </span>
          </Link>
          <p className="text-xs text-muted/50 text-center">
            © 2026 Süleyman Sardoğan · Fırat Üniversitesi Yazılım Mühendisliği
          </p>
          <div className="flex gap-6 text-xs text-muted/60">
            <Link href="/explore" className="hover:text-neon transition-colors">Keşfet</Link>
            <Link href="/login"   className="hover:text-neon transition-colors">Giriş</Link>
            <Link href="/signup"  className="hover:text-neon transition-colors">Kaydol</Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
