"use client";

import { useEffect, useRef, useState } from "react";
import { motion, useScroll, useTransform } from "framer-motion";
import { ArrowRight, Play, Cpu, MapPin, Mic, Eye, ChevronDown } from "lucide-react";
import Link from "next/link";
import Navbar from "@/components/Navbar";
import { getStats, type PlatformStats } from "@/lib/api";

const FEATURES = [
  { icon: Eye,    label: "Computer Vision", desc: "YOLOv8 + Google Vision ile nesne ve landmark tespiti",           color: "#4DFFC3" },
  { icon: Mic,    label: "Ses Analizi",      desc: "Whisper ile Türkçe transkripsiyon ve anahtar kelime tespiti",   color: "#8B5CF6" },
  { icon: Cpu,    label: "NER Pipeline",     desc: "Turkish BERT ile lokasyon entity çıkarımı",                     color: "#FF6B4A" },
  { icon: MapPin, label: "Nominatim + TSP",  desc: "OpenStreetMap geocoding ve optimum rota hesaplama",             color: "#4DFFC3" },
];

const TICKER = ["Halfeti","Kapadokya","Ölüdeniz","Pamukkale","Efes","Göbeklitepe","Antalya","İstanbul","Mardin","Trabzon","Alanya","Bodrum"];

export default function LandingPage() {
  const [stats, setStats] = useState<PlatformStats | null>(null);
  const heroRef = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({ target: heroRef });
  const heroY = useTransform(scrollYProgress, [0, 1], [0, 100]);
  const heroOpacity = useTransform(scrollYProgress, [0,0.7], [1,0]);

  useEffect(() => { getStats().then(setStats).catch(()=>{}); }, []);

  return (
    <div className="min-h-screen overflow-x-hidden">
      <Navbar />

      {/* HERO */}
      <section ref={heroRef} className="relative pt-32 pb-48 px-6 overflow-hidden flex flex-col items-center justify-center">
        <div className="orb w-[700px] h-[700px] bg-neon -top-32 -left-48" style={{opacity:0.06}} />
        <div className="orb w-[500px] h-[500px] bg-violet top-48 -right-32" style={{opacity:0.08}} />
        <div className="orb w-[400px] h-[400px] bg-coral -bottom-16 left-1/3" style={{opacity:0.05}} />

        <motion.div style={{y: heroY, opacity: heroOpacity}} className="relative z-10 text-center px-6 max-w-5xl mx-auto">
          <motion.div initial={{opacity:0,y:20}} animate={{opacity:1,y:0}} transition={{duration:0.6}}
            className="inline-flex items-center gap-2.5 mb-10 px-4 py-2 rounded-full border border-neon/20 bg-neon/5">
            <div className="glow-dot" />
            <span className="text-xs font-mono text-neon tracking-widest uppercase">AI-Powered Travel Intelligence</span>
          </motion.div>

          <motion.h1 initial={{opacity:0,y:30}} animate={{opacity:1,y:0}} transition={{duration:0.7,delay:0.1}}
            className="font-display font-black leading-[0.92] tracking-tight mb-8"
            style={{fontSize:"clamp(3rem,9vw,7.5rem)"}}>
            <span className="text-ice block">Videodan</span>
            <span className="gradient-text block">Gezi Planına</span>
            <span className="text-ice block">Saniyeler İçinde.</span>
          </motion.h1>

          <motion.p initial={{opacity:0,y:20}} animate={{opacity:1,y:0}} transition={{duration:0.6,delay:0.2}}
            className="text-muted text-lg max-w-lg mx-auto mb-10 leading-relaxed">
            Gezi videolarını yükle — AI otomatik olarak OCR, Whisper, NER ile lokasyonları çıkarır ve haritalar.
          </motion.p>

          <motion.div initial={{opacity:0,y:20}} animate={{opacity:1,y:0}} transition={{duration:0.6,delay:0.3}}
            className="flex flex-col sm:flex-row items-center justify-center gap-4">
            <Link href="/login" className="btn-primary px-8 py-4 rounded-xl text-base font-bold flex items-center gap-2 group">
              Hemen Başla <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
            </Link>
            <Link href="/explore" className="btn-neon px-8 py-4 rounded-xl text-base font-bold flex items-center gap-2">
              <Play className="w-4 h-4" /> Gezileri Keşfet
            </Link>
          </motion.div>

          {stats && (
            <motion.div initial={{opacity:0}} animate={{opacity:1}} transition={{delay:0.9}}
              className="flex items-center justify-center gap-8 md:gap-16 mt-24">
              {[
                {val: stats.completed_videos, label:"Video Analiz"},
                {val: stats.total_cities,     label:"Şehir Tespit"},
                {val: stats.total_users,      label:"Kullanıcı"},
              ].map((s,i) => (
                <div key={i} className="text-center">
                  <p className="font-display font-black text-4xl text-neon">{s.val}+</p>
                  <p className="text-[11px] text-muted mt-1.5 tracking-widest uppercase font-mono">{s.label}</p>
                </div>
              ))}
            </motion.div>
          )}
        </motion.div>

        <motion.div animate={{y:[0,8,0]}} transition={{repeat:Infinity,duration:2,ease:"easeInOut"}}
          className="absolute bottom-10 left-1/2 -translate-x-1/2 text-muted/30">
          <ChevronDown className="w-6 h-6" />
        </motion.div>
      </section>

      {/* TICKER */}
      <div className="relative overflow-hidden border-y border-neon/10 bg-neon/[0.02] py-3.5">
        <div className="flex gap-16 whitespace-nowrap" style={{animation:"ticker 25s linear infinite"}}>
          {[...TICKER,...TICKER,...TICKER].map((item,i) => (
            <span key={i} className="text-sm font-mono text-neon/30 flex items-center gap-4">
              <span className="w-1.5 h-1.5 rounded-full bg-neon/30 flex-shrink-0" />
              {item}
            </span>
          ))}
        </div>
        <style>{`@keyframes ticker{from{transform:translateX(0)}to{transform:translateX(-33.33%)}}`}</style>
      </div>

      {/* HOW IT WORKS */}
      <section className="py-36 px-6 max-w-7xl mx-auto">
        <motion.div initial={{opacity:0,y:30}} whileInView={{opacity:1,y:0}} viewport={{once:true}}
          className="text-center mb-20">
          <p className="text-xs font-mono text-neon/50 tracking-widest uppercase mb-4">Pipeline</p>
          <h2 className="font-display font-black text-5xl md:text-6xl text-ice tracking-tight">Nasıl Çalışır?</h2>
        </motion.div>

        <div className="grid md:grid-cols-3 gap-6">
          {[
            {num:"01", title:"Video Yükle",  desc:"Mobil uygulamadan gezi videonu yükle. Max 100MB mp4.",          color:"#4DFFC3"},
            {num:"02", title:"AI Pipeline",  desc:"YOLOv8 → EasyOCR → Whisper → BERT NER → Nominatim → RAG",     color:"#8B5CF6"},
            {num:"03", title:"Plan Hazır",   desc:"Harita, rota, seyahat ipuçları ve PDF export otomatik gelir.", color:"#FF6B4A"},
          ].map((step,i) => (
            <motion.div key={i} initial={{opacity:0,y:30}} whileInView={{opacity:1,y:0}}
              viewport={{once:true}} transition={{delay:i*0.15}}
              className="neon-card rounded-2xl p-8 relative overflow-hidden group">
              <div className="absolute -top-6 -right-4 font-display font-black text-8xl leading-none select-none pointer-events-none"
                style={{color:step.color, opacity:0.06}}>{step.num}</div>
              <div className="absolute top-5 right-5 w-2 h-2 rounded-full"
                style={{background:step.color, boxShadow:`0 0 12px ${step.color}`}} />
              <div className="relative z-10">
                <p className="font-mono text-xs mb-4" style={{color:step.color}}>ADIM {step.num}</p>
                <h3 className="font-display font-bold text-2xl text-ice mb-3">{step.title}</h3>
                <p className="text-muted text-sm leading-relaxed">{step.desc}</p>
              </div>
            </motion.div>
          ))}
        </div>
      </section>

      {/* FEATURES */}
      <section className="py-24 px-6 max-w-7xl mx-auto">
        <motion.div initial={{opacity:0,y:20}} whileInView={{opacity:1,y:0}} viewport={{once:true}}
          className="text-center mb-16">
          <p className="text-xs font-mono text-violet/50 tracking-widest uppercase mb-4">Tech Stack</p>
          <h2 className="font-display font-black text-5xl text-ice tracking-tight">AI Modeller</h2>
        </motion.div>

        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {FEATURES.map((f,i) => (
            <motion.div key={i} initial={{opacity:0,y:20}} whileInView={{opacity:1,y:0}}
              viewport={{once:true}} transition={{delay:i*0.1}}
              className="glass border border-white/5 hover:border-white/10 rounded-2xl p-6 transition-all group">
              <div className="w-11 h-11 rounded-xl flex items-center justify-center mb-5"
                style={{background:`${f.color}10`, border:`1px solid ${f.color}25`}}>
                <f.icon className="w-5 h-5" style={{color:f.color}} />
              </div>
              <h3 className="font-display font-bold text-ice mb-2">{f.label}</h3>
              <p className="text-muted text-xs leading-relaxed">{f.desc}</p>
            </motion.div>
          ))}
        </div>
      </section>

      {/* CTA */}
      <section className="py-24 px-6">
        <motion.div initial={{opacity:0,scale:0.97}} whileInView={{opacity:1,scale:1}} viewport={{once:true}}
          className="animated-border max-w-4xl mx-auto">
          <div className="bg-[#0D1117] rounded-[15px] px-10 py-16 text-center">
            <p className="text-xs font-mono text-neon/50 tracking-widest uppercase mb-6">Fırat Üniversitesi · 2026</p>
            <h2 className="font-display font-black text-4xl md:text-5xl text-ice mb-6 tracking-tight leading-tight">
              Gezi videolarını<br/>
              <span className="gradient-text-neon">akıllı planlara</span> dönüştür.
            </h2>
            <p className="text-muted mb-10 max-w-md mx-auto text-sm leading-relaxed">
              Yazılım Mühendisliği bitirme projesi. Mobil uygulamadan analiz et, web'den keşfet ve paylaş.
            </p>
            <div className="flex flex-col sm:flex-row gap-4 justify-center">
              <Link href="/login" className="btn-primary px-8 py-4 rounded-xl font-bold flex items-center justify-center gap-2 group">
                Başla <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
              </Link>
              <Link href="/explore" className="btn-neon px-8 py-4 rounded-xl font-bold flex items-center justify-center gap-2">
                Gezileri Gör
              </Link>
            </div>
          </div>
        </motion.div>
      </section>

      {/* FOOTER */}
      <footer className="border-t border-white/5 py-10 px-6">
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
          <span className="font-display font-black text-sm text-ice">
            Trip<span className="text-neon">Clip</span> <span className="text-muted font-normal text-xs">AI</span>
          </span>
          <p className="text-xs text-muted text-center">
            © 2026 Süleyman Sardoğan · Fırat Üniversitesi Yazılım Mühendisliği
          </p>
          <div className="flex gap-6 text-xs text-muted">
            <Link href="/explore" className="hover:text-neon transition-colors">Keşfet</Link>
            <Link href="/login"   className="hover:text-neon transition-colors">Giriş</Link>
            <Link href="/signup"  className="hover:text-neon transition-colors">Kaydol</Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
