"use client";

import React, { useEffect, useState, useRef } from "react";
import { motion } from "framer-motion";
import { MapPin, ArrowLeft, Clock, Mic, FileText, Globe2, Navigation, PenLine, Share2 } from "lucide-react";
import Link from "next/link";
import Navbar from "@/components/Navbar";
import { useRouter, useParams } from "next/navigation";
import { getPlan, getVideoProgress, type VideoDetail } from "@/lib/api";
import dynamic from "next/dynamic";

const MapPreview = dynamic(() => import("@/components/MapPreview"), { ssr: false });

/* ─── Stage metadata ─── */
const STAGE_MAP: Record<string, { label: string; icon: string }> = {
  metadata:    { label: "Video Meta Verisi Alınıyor",      icon: "🎬" },
  frames:      { label: "Kareler Çıkarılıyor",             icon: "🎞️" },
  ai_parallel: { label: "Görüntü Analizi Yapılıyor",       icon: "🔍" },
  ner:         { label: "Metin Tanıma (NER)",              icon: "🧠" },
  ner_ocr:     { label: "OCR Sonuçları İşleniyor",         icon: "📝" },
  geocoding:   { label: "Konumlar Eşleştiriliyor",         icon: "🗺️" },
  overpass:    { label: "Mekan Sorgusu Yapılıyor",         icon: "📍" },
  dedup:       { label: "Lokasyonlar Temizleniyor",        icon: "✨" },
  route:       { label: "Rota Optimize Ediliyor",          icon: "🧭" },
  rag:         { label: "Seyahat İpuçları Hazırlanıyor",   icon: "💡" },
};
const STAGE_ORDER = ["metadata","frames","ai_parallel","ner","ner_ocr","geocoding","overpass","dedup","route","rag"];

function formatElapsed(s: number) {
  const m = Math.floor(s / 60);
  const sec = s % 60;
  return m > 0 ? `${m}d ${sec}s` : `${sec}s`;
}

/* ─── Processing screen ─── */
function ProcessingView({ stage, percent, elapsed }: { stage: string; percent: number; elapsed: number }) {
  const info = STAGE_MAP[stage] ?? { label: "İşleniyor…", icon: "⚙️" };
  const currentIdx = STAGE_ORDER.indexOf(stage);
  const R = 68;
  const circ = 2 * Math.PI * R;
  const offset = circ * (1 - percent / 100);

  return (
    <div className="min-h-screen bg-surface flex flex-col">
      <Navbar />
      <div className="flex-1 flex flex-col items-center justify-center px-6 pt-24 pb-16 text-center">

        {/* Circular arc */}
        <div className="relative w-48 h-48 mb-10">
          <svg className="w-full h-full -rotate-90" viewBox="0 0 160 160">
            <circle cx="80" cy="80" r={R} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="8" />
            <circle
              cx="80" cy="80" r={R} fill="none"
              stroke="#4DFFC3" strokeWidth="8" strokeLinecap="round"
              strokeDasharray={circ}
              strokeDashoffset={offset}
              style={{ transition: "stroke-dashoffset 0.6s ease" }}
            />
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span className="text-4xl mb-0.5">{info.icon}</span>
            <span className="text-3xl font-black text-neon">{percent}%</span>
          </div>
        </div>

        {/* Stage label */}
        <h2 className="text-2xl font-black text-ice tracking-tight mb-2">Videonuz Analiz Ediliyor</h2>
        <p className="text-muted text-sm font-medium mb-10">{info.label}</p>

        {/* Stage dots */}
        <div className="flex gap-2 mb-8">
          {STAGE_ORDER.map((s, i) => (
            <div
              key={s}
              className={`rounded-full transition-all duration-300 ${
                i < currentIdx  ? "w-2 h-2 bg-neon"
                : i === currentIdx ? "w-3 h-3 bg-neon animate-pulse shadow-neon"
                : "w-2 h-2 bg-white/10"
              }`}
            />
          ))}
        </div>

        {/* Elapsed */}
        <p className="text-muted text-xs">⏱ {formatElapsed(elapsed)} geçti · sayfa otomatik yenilenecek</p>

        {/* Subtle progress bar */}
        <div className="mt-8 w-64 h-1 bg-white/5 rounded-full overflow-hidden">
          <div
            className="h-full bg-neon rounded-full transition-all duration-700"
            style={{ width: `${percent}%` }}
          />
        </div>
      </div>
    </div>
  );
}

/* ─── Main page ─── */
export default function AnalysisResultPage() {
  const router  = useRouter();
  const params  = useParams();
  const [video, setVideo]               = useState<VideoDetail | null>(null);
  const [loading, setLoading]           = useState(true);
  const [error, setError]               = useState("");
  const [progressStage, setProgressStage]   = useState("metadata");
  const [progressPercent, setProgressPercent] = useState(0);
  const [elapsed, setElapsed]           = useState(0);
  const pollRef    = useRef<ReturnType<typeof setInterval> | null>(null);
  const elapsedRef = useRef<ReturnType<typeof setInterval> | null>(null);

  /* Initial fetch */
  useEffect(() => {
    const id = Number(params.id);
    if (!id || isNaN(id)) { setError("Geçersiz ID"); setLoading(false); return; }
    getPlan(id)
      .then(setVideo)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, [params.id]);

  /* Polling — only when processing */
  useEffect(() => {
    if (!video || video.status !== "processing") return;
    const id = Number(params.id);

    elapsedRef.current = setInterval(() => setElapsed(p => p + 1), 1000);

    let iterations = 0;
    pollRef.current = setInterval(async () => {
      if (++iterations > 200) { clearInterval(pollRef.current!); return; }

      try {
        const prog = await getVideoProgress(id);
        setProgressStage(prog.stage  || "processing");
        setProgressPercent(prog.percent ?? 0);
      } catch { /* network blip — keep showing last value */ }

      try {
        const updated = await getPlan(id);
        if (updated.status !== "processing") setVideo(updated);
      } catch { /* keep polling */ }
    }, 3000);

    return () => {
      if (pollRef.current)    clearInterval(pollRef.current);
      if (elapsedRef.current) clearInterval(elapsedRef.current);
    };
  }, [video?.status, params.id]);

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

  if (video.status === "processing") {
    return <ProcessingView stage={progressStage} percent={progressPercent} elapsed={elapsed} />;
  }

  if (video.status === "failed") {
    return (
      <div className="min-h-screen bg-surface flex flex-col items-center justify-center gap-4">
        <p className="text-4xl">⚠️</p>
        <p className="text-ice font-bold">Video işlenirken hata oluştu</p>
        <button onClick={() => router.back()} className="text-neon hover:underline text-sm">Geri Dön</button>
      </div>
    );
  }

  /* ─── Results ─── */
  const ai           = video.ai_results;
  const locations    = ai?.nominatim?.deduplicated_locations ?? [];
  const ocrTexts     = ai?.ocr?.extracted_texts ?? [];
  const nerLocations = ai?.ner?.extracted_locations ?? [];
  const ocrPois      = ai?.ocr_pois ?? [];
  const transcript   = ai?.audio?.transcription?.transcript;
  const tips         = ai?.rag?.travel_tips?.tips ?? [];
  const summary      = ai?.rag?.travel_tips?.summary;
  const totalDistance = ai?.route?.optimized_route?.total_distance_km;

  return (
    <div className="min-h-screen bg-surface text-ice">
      <Navbar />

      <main className="pt-24 pb-20 px-6 max-w-screen-xl mx-auto">
        <div className="flex items-center justify-between mb-8">
          <button
            onClick={() => router.back()}
            className="flex items-center gap-2 text-muted hover:text-ice transition-all group font-bold uppercase tracking-widest text-[10px]"
          >
            <ArrowLeft className="w-4 h-4 group-hover:-translate-x-1 transition-transform" /> Geri
          </button>
          <div className="flex items-center gap-3">
            <Link
              href={`/editor/${params.id}`}
              className="flex items-center gap-2 px-5 py-2.5 bg-neon/10 border border-neon/30 text-neon rounded-full text-[10px] font-black uppercase tracking-widest hover:bg-neon/20 transition-all"
            >
              <PenLine className="w-3.5 h-3.5" /> Planı Düzenle
            </Link>
            <Link
              href={`/share/${params.id}`}
              className="flex items-center gap-2 px-5 py-2.5 bg-violet/10 border border-violet/30 text-violet rounded-full text-[10px] font-black uppercase tracking-widest hover:bg-violet/20 transition-all"
            >
              <Share2 className="w-3.5 h-3.5" /> Paylaş
            </Link>
          </div>
        </div>

        {/* Header */}
        <div className="mb-8">
          <h1 className="text-4xl font-black tracking-tighter mb-2">
            {locations.length > 0
              ? locations[0].original_name.charAt(0).toUpperCase() + locations[0].original_name.slice(1) + " Gezi Planı"
              : "Gezi Planı"}
          </h1>
          <div className="flex flex-wrap items-center gap-6 text-sm text-muted">
            {ai?.processing_time && <span className="flex items-center gap-1"><Clock className="w-4 h-4" /> {Math.round(ai.processing_time)}s analiz</span>}
            {video.duration      && <span className="flex items-center gap-1"><FileText className="w-4 h-4" /> {video.duration}s video</span>}
            {totalDistance       && <span className="flex items-center gap-1"><Navigation className="w-4 h-4" /> {Math.round(totalDistance)} km rota</span>}
            {ai?.detections?.count && <span className="flex items-center gap-1"><Globe2 className="w-4 h-4" /> {ai.detections.count} nesne</span>}
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">

          {/* Sol Panel */}
          <div className="lg:col-span-4 space-y-6">

            {locations.length > 0 && (
              <Card title="🏙️ Bulunan Şehirler">
                <div className="space-y-3">
                  {locations.map((loc, i) => (
                    <div key={i} className="flex items-start gap-3">
                      <MapPin className="w-4 h-4 text-neon mt-0.5 flex-shrink-0" />
                      <div>
                        <p className="font-semibold text-sm">{loc.original_name.charAt(0).toUpperCase() + loc.original_name.slice(1)}</p>
                        <p className="text-xs text-muted">{loc.place_data?.name}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </Card>
            )}

            {locations.length === 0 && nerLocations.length > 0 && (
              <Card title="📍 Tespit Edilen Yerler">
                <div className="flex flex-wrap gap-2">
                  {nerLocations.map((loc, i) => (
                    <span key={i} className="tag">{loc}</span>
                  ))}
                </div>
              </Card>
            )}

            {tips.length > 0 && (
              <Card title="💡 Seyahat İpuçları">
                <div className="space-y-3">
                  {tips.map((tip: any, i: number) => (
                    <div key={i} className="p-3 bg-white/5 rounded-xl">
                      <p className="text-xs font-bold text-neon mb-1">{tip.location}</p>
                      <p className="text-xs text-muted leading-relaxed">{tip.tip}</p>
                    </div>
                  ))}
                </div>
              </Card>
            )}

            {summary && (
              <Card title="📖 Özet">
                <p className="text-sm text-muted leading-relaxed">{summary}</p>
              </Card>
            )}
          </div>

          {/* Sağ Panel */}
          <div className="lg:col-span-8 space-y-6">

            {locations.length > 0 && (
              <Card title="🗺️ Harita">
                <div className="h-[350px] rounded-xl overflow-hidden">
                  <MapPreview locations={locations} />
                </div>
              </Card>
            )}

            {(ocrPois.length > 0 || ocrTexts.length > 0) && (
              <Card title="📝 Videodaki Yazılar">
                <div className="flex flex-wrap gap-2">
                  {(ocrPois.length > 0 ? ocrPois : ocrTexts).map((text, i) => (
                    <span key={i} className="bg-white/5 border border-white/10 text-ice text-xs px-3 py-1.5 rounded-lg">{text}</span>
                  ))}
                </div>
              </Card>
            )}

            {transcript && (
              <Card title="🎙️ Ses Transkripsiyonu">
                <div className="flex items-start gap-3">
                  <Mic className="w-4 h-4 text-neon mt-0.5 flex-shrink-0" />
                  <p className="text-sm text-muted leading-relaxed">{transcript}</p>
                </div>
              </Card>
            )}

            {locations.length === 0 && nerLocations.length === 0 && ocrTexts.length === 0 && (
              <Card title="ℹ️ Bilgi">
                <p className="text-sm text-muted">Bu videodan lokasyon bilgisi çıkarılamadı. Türkçe yazı veya yer adı içeren videolar deneyin.</p>
              </Card>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      className="neon-card rounded-2xl p-6"
    >
      <h3 className="font-bold text-sm mb-4 text-ice">{title}</h3>
      {children}
    </motion.div>
  );
}
