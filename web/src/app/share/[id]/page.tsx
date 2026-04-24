"use client";

import React, { useState, useEffect } from "react";
import { motion } from "framer-motion";
import {
  Map as MapIcon,
  Share2,
  BrainCircuit,
  Star,
  Sun,
  Lightbulb,
  MapPin,
  ArrowLeft,
  Navigation,
  Clock,
  Camera,
} from "lucide-react";
import Navbar from "@/components/Navbar";
import { useParams, useRouter } from "next/navigation";
import { getPlan, type VideoDetail } from "@/lib/api";

function capitalize(s: string) {
  return s.charAt(0).toUpperCase() + s.slice(1);
}

/* ─── Hero görselleri — seyahat temalı stock fotolar (data değil tasarım öğesi) ─── */
const HERO_IMAGES = [
  "https://images.unsplash.com/photo-1533105079780-92b9be482077?auto=format&fit=crop&q=80&w=1200",
  "https://images.unsplash.com/photo-1476514525535-07fb3b4ae5f1?auto=format&fit=crop&q=80&w=1200",
  "https://images.unsplash.com/photo-1488646953014-85cb44e25828?auto=format&fit=crop&q=80&w=1200",
  "https://images.unsplash.com/photo-1530789253388-582c481c54b0?auto=format&fit=crop&q=80&w=1200",
];

const TIP_ICONS = [Star, Sun, Lightbulb, Camera];

export default function SharePage() {
  const params = useParams();
  const router = useRouter();
  const [video,   setVideo]   = useState<VideoDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState("");
  const [copied,  setCopied]  = useState(false);

  useEffect(() => {
    const id = Number(params.id);
    if (!id || isNaN(id)) { setError("Geçersiz ID"); setLoading(false); return; }
    getPlan(id)
      .then(setVideo)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, [params.id]);

  /* ─── States ─── */
  if (loading) {
    return (
      <div className="min-h-screen bg-surface flex items-center justify-center">
        <div className="w-8 h-8 border-2 border-neon border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (error || !video) {
    return (
      <div className="min-h-screen bg-surface flex flex-col items-center justify-center gap-4">
        <p className="text-red-400 text-sm">{error || "Plan bulunamadı"}</p>
        <button onClick={() => router.back()} className="text-neon hover:underline text-sm">Geri Dön</button>
      </div>
    );
  }

  const ai           = video.ai_results;
  const locations    = ai?.nominatim?.deduplicated_locations ?? [];
  const tips         = ai?.rag?.travel_tips?.tips ?? [];
  const summary      = ai?.rag?.travel_tips?.summary;
  const totalDist    = ai?.route?.optimized_route?.total_distance_km;
  const firstCity    = locations[0]?.original_name ?? "";
  const tripTitle    = firstCity ? `${capitalize(firstCity)} Seyahati` : "Gezi Planı";
  const heroImg      = HERO_IMAGES[Number(params.id) % HERO_IMAGES.length];

  const stats = [
    { label: "Toplam Durak",  value: String(locations.length || "—") },
    { label: "Mesafe",        value: totalDist ? `${Math.round(totalDist)} km` : "—" },
    { label: "Video Süresi",  value: video.duration ? `${video.duration}s` : "—" },
    { label: "Şehir",        value: String(locations.length > 0 ? new Set(locations.map(l => l.place_data?.name?.split(",")[0])).size : "—") },
  ];

  function handleShare() {
    navigator.clipboard.writeText(window.location.href).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  function openMaps() {
    if (locations.length === 0) return;
    const first = locations[0].place_data?.location;
    if (first) window.open(`https://www.google.com/maps?q=${first.lat},${first.lng}`, "_blank");
  }

  return (
    <div className="min-h-screen bg-surface font-sans text-ice">
      <Navbar />

      <main className="max-w-screen-2xl mx-auto px-6 pb-32 pt-24">

        {/* Back */}
        <button
          onClick={() => router.back()}
          className="flex items-center gap-2 text-muted hover:text-ice transition-all mb-6 text-[10px] font-black uppercase tracking-widest"
        >
          <ArrowLeft className="w-3 h-3" /> Geri
        </button>

        {/* ── Hero ── */}
        <section className="relative w-full h-[530px] rounded-[3rem] overflow-hidden mb-12 shadow-2xl group">
          <img
            src={heroImg}
            className="w-full h-full object-cover transition-transform duration-1000 group-hover:scale-105"
            alt={tripTitle}
          />
          <div className="absolute inset-0 bg-gradient-to-t from-surface/95 via-surface/20 to-transparent" />

          <div className="absolute bottom-0 left-0 p-12 w-full flex flex-col md:flex-row md:items-end justify-between gap-8">
            <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="max-w-3xl">
              <span className="inline-block px-4 py-2 bg-neon text-surface rounded-full text-xs font-bold uppercase tracking-[0.2em] mb-6 shadow-neon">
                TripClip AI · {new Date(video.created_at).toLocaleDateString("tr-TR", { month: "long", year: "numeric" })}
              </span>
              <h1 className="text-5xl md:text-7xl font-black text-ice font-display tracking-tighter leading-none mb-6">
                {tripTitle}
              </h1>
              {summary && (
                <p className="text-ice/80 text-xl leading-relaxed max-w-xl opacity-90">{summary}</p>
              )}
            </motion.div>

            <div className="flex flex-wrap gap-4 relative z-10">
              <button
                onClick={openMaps}
                className="bg-neon text-surface px-10 py-5 rounded-full font-bold shadow-neon flex items-center gap-3 transition-all hover:scale-105 active:scale-95"
              >
                <MapIcon className="w-5 h-5" /> Google Maps'te Aç
              </button>
              <button
                onClick={handleShare}
                className="bg-white/10 backdrop-blur-xl border border-white/20 text-ice px-10 py-5 rounded-full font-bold flex items-center gap-3 transition-all hover:bg-white/20"
              >
                <Share2 className="w-5 h-5" /> {copied ? "Kopyalandı ✓" : "Linki Paylaş"}
              </button>
            </div>
          </div>
        </section>

        {/* ── Content grid ── */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-12">

          {/* Main (left) */}
          <div className="lg:col-span-8 space-y-16">

            {/* Stats */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
              {stats.map((stat, i) => (
                <div key={i} className="neon-card p-8 rounded-[2rem] flex flex-col items-center justify-center text-center">
                  <span className="text-neon font-black text-4xl mb-2">{stat.value}</span>
                  <span className="text-muted font-bold text-[10px] uppercase tracking-widest">{stat.label}</span>
                </div>
              ))}
            </div>

            {/* Locations list */}
            {locations.length > 0 && (
              <div className="neon-card p-12 rounded-[3rem] relative overflow-hidden">
                <h3 className="text-3xl font-black font-display mb-8 text-neon flex items-center gap-4 tracking-tighter">
                  <MapPin className="text-neon w-8 h-8" /> Gezi Güzergahı
                </h3>
                <div className="relative space-y-6">
                  <div className="absolute left-[11px] top-2 bottom-2 w-px bg-white/10" />
                  {locations.map((loc, i) => (
                    <div key={i} className="flex items-start gap-6 relative">
                      <div className={`w-6 h-6 rounded-full flex-shrink-0 mt-0.5 flex items-center justify-center text-[10px] font-black ${i === 0 ? "bg-neon text-surface" : "bg-white/10 text-muted"}`}>
                        {i + 1}
                      </div>
                      <div>
                        <p className="font-black text-ice">{capitalize(loc.original_name)}</p>
                        <p className="text-muted text-xs mt-0.5">{loc.place_data?.name}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Route stats */}
            {(totalDist || video.duration) && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {totalDist && (
                  <div className="neon-card p-8 rounded-[2.5rem] flex items-center gap-6">
                    <div className="w-14 h-14 rounded-2xl bg-neon/10 flex items-center justify-center text-neon">
                      <Navigation className="w-7 h-7" />
                    </div>
                    <div>
                      <p className="font-black text-2xl text-ice">{Math.round(totalDist)} km</p>
                      <p className="text-muted text-xs uppercase tracking-widest">Toplam Rota</p>
                    </div>
                  </div>
                )}
                {video.duration && (
                  <div className="neon-card p-8 rounded-[2.5rem] flex items-center gap-6">
                    <div className="w-14 h-14 rounded-2xl bg-violet/10 flex items-center justify-center text-violet">
                      <Clock className="w-7 h-7" />
                    </div>
                    <div>
                      <p className="font-black text-2xl text-ice">{video.duration}s</p>
                      <p className="text-muted text-xs uppercase tracking-widest">Video Süresi</p>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* AI Insights (right) */}
          <aside className="lg:col-span-4 space-y-8">

            {/* AI insights card */}
            <div className="bg-card border border-neon/15 p-10 rounded-[3rem] shadow-neon relative overflow-hidden">
              <div className="absolute inset-0 opacity-5 pointer-events-none" style={{ backgroundImage: "radial-gradient(#4DFFC3 1px, transparent 1px)", backgroundSize: "30px 30px" }} />
              <div className="relative z-10">
                <div className="flex items-center gap-3 mb-8">
                  <BrainCircuit className="text-neon w-8 h-8" />
                  <h3 className="text-lg font-black font-display uppercase tracking-[0.2em] text-neon">AI Seyahat İpuçları</h3>
                </div>
                {tips.length > 0 ? (
                  <ul className="space-y-8">
                    {tips.slice(0, 3).map((tip: any, i: number) => {
                      const Icon = TIP_ICONS[i % TIP_ICONS.length];
                      return (
                        <li key={i} className="flex gap-5">
                          <Icon className="text-neon w-6 h-6 shrink-0 mt-1" />
                          <div>
                            <p className="text-neon text-xs font-black uppercase tracking-widest mb-1">{tip.location}</p>
                            <p className="text-ice/80 text-sm leading-relaxed font-medium">{tip.tip}</p>
                          </div>
                        </li>
                      );
                    })}
                  </ul>
                ) : (
                  <p className="text-muted text-sm">Bu video için AI seyahat ipucu oluşturuldu.</p>
                )}
              </div>
            </div>

            {/* Map placeholder / share card */}
            <div className="neon-card rounded-[3rem] overflow-hidden p-3 group">
              <div
                className="rounded-[2.5rem] h-64 relative shadow-inner overflow-hidden"
                style={{ background: "linear-gradient(135deg, #0D1117, #1A2535)" }}
              >
                <div className="absolute inset-0 opacity-20" style={{ backgroundImage: "radial-gradient(#4DFFC3 1px, transparent 1px)", backgroundSize: "20px 20px" }} />
                {locations.slice(0, 4).map((loc, i) => (
                  <div
                    key={i}
                    className="absolute w-4 h-4 rounded-full bg-neon shadow-neon animate-pulse"
                    style={{
                      left:  `${20 + (i * 18) % 60}%`,
                      top:   `${25 + (i * 15) % 50}%`,
                      animationDelay: `${i * 0.5}s`,
                    }}
                  />
                ))}
                <div className="absolute inset-0 flex items-center justify-center">
                  <div className="bg-surface/90 backdrop-blur-md p-4 rounded-2xl shadow-2xl border border-neon/20">
                    <MapPin className="text-neon w-6 h-6 animate-bounce" />
                  </div>
                </div>
              </div>
              <div className="p-8">
                <h4 className="font-black text-2xl text-ice mb-3 tracking-tighter">{locations.length} Lokasyon</h4>
                <p className="text-sm text-muted mb-8 opacity-70">AI tarafından optimize edilmiş rota.</p>
                <button
                  onClick={openMaps}
                  className="w-full py-5 border-2 border-neon/20 text-neon font-black rounded-[1.5rem] hover:bg-neon hover:text-surface transition-all text-sm uppercase tracking-widest"
                >
                  Haritada Gör
                </button>
              </div>
            </div>

            {/* Quick share tip */}
            <div
              onClick={handleShare}
              className="neon-card p-8 rounded-[2.5rem] flex items-center gap-5 cursor-pointer hover:border-neon/40 transition-all"
            >
              <div className="w-14 h-14 rounded-2xl bg-neon/10 flex items-center justify-center text-neon shadow-inner">
                <Lightbulb className="w-6 h-6" />
              </div>
              <div>
                <p className="font-black text-ice text-lg tracking-tight">Linki Kopyala</p>
                <p className="text-xs text-muted opacity-70 font-medium">
                  {copied ? "Panoya kopyalandı ✓" : "Arkadaşlarınla paylaş"}
                </p>
              </div>
            </div>
          </aside>
        </div>
      </main>
    </div>
  );
}
