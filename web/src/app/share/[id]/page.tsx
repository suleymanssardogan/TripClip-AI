"use client";
/* eslint-disable @typescript-eslint/no-explicit-any */

import React, { useState, useEffect, useRef } from "react";
import { motion } from "framer-motion";
import {
  Map as MapIcon,
  Share2,
  Sparkles,
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
import QRShareCard from "@/components/QRShareCard";
import { useParams, useRouter } from "next/navigation";
import { getPlan, trackAnalyticsEvent, markShareReferral, type VideoDetail } from "@/lib/api";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";

function capitalize(s: string) {
  return s.charAt(0).toUpperCase() + s.slice(1);
}

const TIP_ICONS = [Star, Sun, Lightbulb, Camera];

/** Decorative scenic illustration — matches the landing hero motif. Never
 *  a stand-in stock photo for the actual place, since we don't have one. */
function SceneHero({ className = "" }: { className?: string }) {
  return (
    <div className={`relative overflow-hidden ${className}`}
      style={{ background: "linear-gradient(180deg, #12141C, #2B2320)" }}>
      <svg viewBox="0 0 1200 530" preserveAspectRatio="xMidYMid slice" className="absolute inset-0 w-full h-full">
        <circle cx="980" cy="130" r="90" fill="#FFC352" />
        <path d="M0 320 Q300 260 600 310 T1200 290 V530 H0 Z" fill="#23262E" />
        <path d="M0 390 Q350 350 650 380 T1200 365 V530 H0 Z" fill="#181A1F" />
        <g><ellipse cx="380" cy="230" rx="50" ry="64" fill="#FFB020" /><rect x="364" y="290" width="30" height="18" rx="3" fill="#3a2a12" /></g>
        <g><ellipse cx="560" cy="160" rx="36" ry="46" fill="#EDE7DC" /></g>
        <g><ellipse cx="700" cy="270" rx="26" ry="34" fill="#C4573A" /></g>
      </svg>
    </div>
  );
}

export default function SharePage() {
  const params = useParams();
  const router = useRouter();
  const [video,   setVideo]   = useState<VideoDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState("");
  const [copied,  setCopied]  = useState(false);

  // React StrictMode efekti geliştirmede iki kez çalıştırır — event'in yalnızca
  // bir kez ateşlenmesini garanti eder (bkz. spesifikasyonun "prevent duplicate
  // events" gereksinimi, sunucu tarafında karşılığı yok çünkü bu istemci-taraflı bir mount).
  const openedTracked = useRef(false);

  useEffect(() => {
    const id = Number(params.id);
    if (!id || isNaN(id)) {
      setTimeout(() => {
        setError("Geçersiz ID");
        setLoading(false);
      }, 0);
      return;
    }
    getPlan(id)
      .then(res => {
        setTimeout(() => {
          setVideo(res);
          setLoading(false);
        }, 0);
        // Yalnızca sayfa gerçekten yüklendiğinde "açıldı" sayılır — 404/hata
        // durumunda kullanıcı paylaşılan içeriği hiç görmedi.
        if (!openedTracked.current) {
          openedTracked.current = true;
          trackAnalyticsEvent("shared_trip_opened", id, "direct_link");
          markShareReferral(id);
        }
      })
      .catch(e => {
        setTimeout(() => {
          setError(e.message);
          setLoading(false);
        }, 0);
      });
  }, [params.id]);

  /* ─── States ─── */
  if (loading) {
    return (
      <div className="min-h-screen bg-bg flex items-center justify-center">
        <div className="w-8 h-8 border-2 border-accent border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (error || !video) {
    return (
      <div className="min-h-screen bg-bg flex flex-col items-center justify-center gap-4">
        <p className="text-destructive text-sm">{error || "Plan bulunamadı"}</p>
        <button onClick={() => router.back()} className="text-accent-text hover:underline text-sm">Geri Dön</button>
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

  const stats = [
    { label: "Toplam Durak",  value: String(locations.length || "—") },
    { label: "Mesafe",        value: totalDist ? `${Math.round(totalDist)} km` : "—" },
    { label: "Video Süresi",  value: video.duration ? `${video.duration}s` : "—" },
    { label: "Şehir",        value: String(locations.length > 0 ? new Set(locations.map(l => l.place_data?.name?.split(",")[0])).size : "—") },
  ];

  function handleShare(source: string) {
    navigator.clipboard.writeText(window.location.href).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
      trackAnalyticsEvent("shared_trip_link_copied", Number(params.id), source);
    });
  }

  function openMaps() {
    if (locations.length === 0) return;
    const first = locations[0].place_data?.location;
    if (first) window.open(`https://www.google.com/maps?q=${first.lat},${first.lng}`, "_blank");
  }

  return (
    <div className="min-h-screen bg-bg font-sans text-text">
      <Navbar />

      <main className="max-w-screen-2xl mx-auto px-6 pb-32 pt-24">

        {/* Back */}
        <button
          onClick={() => router.back()}
          className="flex items-center gap-2 text-text-tertiary hover:text-text transition-all mb-6 text-[10px] font-black uppercase tracking-widest"
        >
          <ArrowLeft className="w-3 h-3" /> Geri
        </button>

        {/* ── Hero ── */}
        <section className="relative w-full h-[420px] rounded-lg overflow-hidden mb-12">
          <SceneHero className="absolute inset-0" />
          <div className="absolute inset-0 bg-gradient-to-t from-bg/95 via-bg/20 to-transparent" />

          <div className="absolute bottom-0 left-0 p-10 w-full flex flex-col md:flex-row md:items-end justify-between gap-8">
            <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="max-w-3xl">
              <span className="inline-block px-4 py-2 bg-accent text-on-accent rounded-full font-mono text-xs font-bold uppercase tracking-[0.2em] mb-6">
                TripClip AI · {new Date(video.created_at).toLocaleDateString("tr-TR", { month: "long", year: "numeric" })}
              </span>
              <h1 className="text-4xl md:text-6xl font-black text-text font-display tracking-tighter leading-none mb-4">
                {tripTitle}
              </h1>
              {summary && (
                <p className="text-text/80 text-lg leading-relaxed max-w-xl">{summary}</p>
              )}
            </motion.div>

            <div className="flex flex-wrap gap-4 relative z-10">
              <Button
                onClick={openMaps}
                className="rounded-full px-8 py-4 transition-transform hover:scale-105 active:scale-95"
              >
                <MapIcon className="w-5 h-5" /> Google Maps&apos;te Aç
              </Button>
              <Button
                variant="outline" onClick={() => handleShare("hero_button")}
                className="rounded-full px-8 py-4 bg-surface/80 backdrop-blur-xl"
              >
                <Share2 className="w-5 h-5" /> {copied ? "Kopyalandı ✓" : "Linki Paylaş"}
              </Button>
            </div>
          </div>
        </section>

        {/* ── Content grid ── */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-12">

          {/* Main (left) */}
          <div className="lg:col-span-8 space-y-12">

            {/* Stats */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {stats.map((stat, i) => (
                <Card key={i} className="p-6 flex flex-col items-center justify-center text-center">
                  <span className="font-mono text-accent-text font-semibold text-3xl mb-1 tabular-nums">{stat.value}</span>
                  <span className="text-text-tertiary font-semibold text-[10px] uppercase tracking-widest">{stat.label}</span>
                </Card>
              ))}
            </div>

            {/* Locations list */}
            {locations.length > 0 && (
              <Card className="p-10">
                <h3 className="text-2xl font-black font-display mb-8 text-text flex items-center gap-3 tracking-tight">
                  <MapPin className="text-route w-6 h-6" /> Gezi Güzergahı
                </h3>
                <div className="relative space-y-6">
                  <div className="absolute left-[11px] top-2 bottom-2 w-px bg-border" />
                  {locations.map((loc, i) => (
                    <div key={i} className="flex items-start gap-5 relative">
                      <div className={`w-6 h-6 rounded-full flex-shrink-0 mt-0.5 flex items-center justify-center text-[10px] font-black ${i === 0 ? "bg-accent text-on-accent" : "bg-surface2 text-text-tertiary"}`}>
                        {i + 1}
                      </div>
                      <div>
                        <p className="font-bold text-text">{capitalize(loc.original_name)}</p>
                        <p className="text-text-tertiary text-xs mt-0.5">{loc.place_data?.name}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </Card>
            )}

            {/* Route stats */}
            {(totalDist || video.duration) && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {totalDist && (
                  <Card className="p-6 flex items-center gap-5">
                    <div className="w-12 h-12 rounded-md bg-route/10 border border-route/20 flex items-center justify-center text-route">
                      <Navigation className="w-6 h-6" />
                    </div>
                    <div>
                      <p className="font-bold text-xl text-text">{Math.round(totalDist)} km</p>
                      <p className="text-text-tertiary text-xs uppercase tracking-widest">Toplam Rota</p>
                    </div>
                  </Card>
                )}
                {video.duration && (
                  <Card className="p-6 flex items-center gap-5">
                    <div className="w-12 h-12 rounded-md bg-accent/10 border border-accent/20 flex items-center justify-center text-accent-text">
                      <Clock className="w-6 h-6" />
                    </div>
                    <div>
                      <p className="font-bold text-xl text-text">{video.duration}s</p>
                      <p className="text-text-tertiary text-xs uppercase tracking-widest">Video Süresi</p>
                    </div>
                  </Card>
                )}
              </div>
            )}
          </div>

          {/* AI Insights (right) */}
          <aside className="lg:col-span-4 space-y-6">

            {/* QR kod paylaşım kartı */}
            <QRShareCard
              url={typeof window !== "undefined" ? window.location.href : ""}
              title={`${tripTitle} • QR Paylaş`}
              onCopy={() => trackAnalyticsEvent("shared_trip_link_copied", Number(params.id), "qr_card")}
            />

            {/* AI insights card */}
            <Card className="p-8">
              <div className="flex items-center gap-3 mb-6">
                <Sparkles className="text-accent-text w-6 h-6" />
                <h3 className="text-sm font-black font-display uppercase tracking-[0.2em] text-accent-text">AI Seyahat İpuçları</h3>
              </div>
              {tips.length > 0 ? (
                <ul className="space-y-6">
                  {tips.slice(0, 3).map((tip: any, i: number) => {
                    const Icon = TIP_ICONS[i % TIP_ICONS.length];
                    return (
                      <li key={i} className="flex gap-4">
                        <Icon className="text-route w-5 h-5 shrink-0 mt-1" />
                        <div>
                          <p className="text-text text-xs font-bold uppercase tracking-widest mb-1">{tip.location}</p>
                          <p className="text-text-secondary text-sm leading-relaxed">{tip.tip}</p>
                        </div>
                      </li>
                    );
                  })}
                </ul>
              ) : (
                <p className="text-text-tertiary text-sm">Bu video için AI seyahat ipucu oluşturuldu.</p>
              )}
            </Card>

            {/* Map placeholder / share card */}
            <Card>
              <div className="h-52 relative overflow-hidden bg-surface2">
                {locations.slice(0, 4).map((loc, i) => (
                  <div
                    key={i}
                    className="absolute w-3.5 h-3.5 rounded-full bg-route animate-pulse"
                    style={{
                      left:  `${20 + (i * 18) % 60}%`,
                      top:   `${25 + (i * 15) % 50}%`,
                      animationDelay: `${i * 0.5}s`,
                    }}
                  />
                ))}
                <div className="absolute inset-0 flex items-center justify-center">
                  <div className="bg-bg/90 backdrop-blur-md p-4 rounded-md border border-border-strong">
                    <MapPin className="text-route w-6 h-6" />
                  </div>
                </div>
              </div>
              <div className="p-6">
                <h4 className="font-bold text-xl text-text mb-2 tracking-tight">{locations.length} Lokasyon</h4>
                <p className="text-sm text-text-tertiary mb-6">AI tarafından optimize edilmiş rota.</p>
                <Button
                  variant="outline" onClick={openMaps}
                  className="w-full py-3.5 border-route/25 text-route hover:bg-route hover:text-bg text-sm uppercase tracking-widest"
                >
                  Haritada Gör
                </Button>
              </div>
            </Card>

            {/* Quick share tip */}
            <Card
              onClick={() => handleShare("sidebar_card")}
              className="p-6 flex items-center gap-4 cursor-pointer hover:border-border-strong transition-colors"
            >
              <div className="w-12 h-12 rounded-md bg-accent/10 border border-accent/20 flex items-center justify-center text-accent-text">
                <Lightbulb className="w-5 h-5" />
              </div>
              <div>
                <p className="font-bold text-text">Linki Kopyala</p>
                <p className="text-xs text-text-tertiary">
                  {copied ? "Panoya kopyalandı ✓" : "Arkadaşlarınla paylaş"}
                </p>
              </div>
            </Card>
          </aside>
        </div>
      </main>
    </div>
  );
}
