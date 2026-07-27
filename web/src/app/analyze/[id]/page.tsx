"use client";
/* eslint-disable @typescript-eslint/no-explicit-any */

import React, { useEffect, useState, useRef } from "react";
import { motion } from "framer-motion";
import {
  MapPin, ArrowLeft, Clock, Mic, FileText, Globe2, Navigation, PenLine, Share2, Download,
  Sparkles, Landmark, Map, Lightbulb, Check, AlertTriangle, Info, BookOpen, Building2,
} from "lucide-react";
import Link from "next/link";
import Navbar from "@/components/Navbar";
import AIStatsCard from "@/components/AIStatsCard";
import { useRouter, useParams } from "next/navigation";
import { getPlan, getVideoProgress, type VideoDetail } from "@/lib/api";
import dynamic from "next/dynamic";
import { Card as UICard } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";

const MapPreview = dynamic(() => import("@/components/MapPreview"), { ssr: false });

/* ─────────────────────────────────────────────────────────────────────────
   Backend reports progress against 10 raw pipeline stages. We group them
   into the 6 user-facing stages from the product brief so the ring never
   resets mid-analysis, and the stage list reads as a story, not internals.
   ───────────────────────────────────────────────────────────────────────── */
const STAGE_ORDER = ["metadata","frames","ai_parallel","ner","ner_ocr","geocoding","overpass","dedup","route","rag"];

const STAGE_BUCKETS: { label: string; icon: React.ComponentType<{ className?: string }> }[] = [
  { label: "Görüntü Analizi",   icon: Sparkles },
  { label: "Yer Tespiti",       icon: Landmark },
  { label: "Konum Eşleştirme",  icon: MapPin },
  { label: "Gezi Planlama",     icon: Navigation },
  { label: "Harita Oluşturma",  icon: Map },
  { label: "Seyahat İpuçları",  icon: Lightbulb },
];

const BUCKET_RANGES = [[0,2],[3,4],[5,6],[7,7],[8,8],[9,9]];

function bucketIndexOf(stage: string): number {
  const rawIdx = STAGE_ORDER.indexOf(stage);
  if (rawIdx < 0) return 0;
  const i = BUCKET_RANGES.findIndex(([lo, hi]) => rawIdx >= lo && rawIdx <= hi);
  return i < 0 ? 0 : i;
}

function overallPercentOf(stage: string, percent: number): number {
  const rawIdx = STAGE_ORDER.indexOf(stage);
  if (rawIdx < 0) return percent;
  return Math.round(((rawIdx + percent / 100) / STAGE_ORDER.length) * 100);
}

function formatElapsed(s: number) {
  const m = Math.floor(s / 60);
  const sec = s % 60;
  return m > 0 ? `${m}d ${sec}s` : `${sec}s`;
}

/* ─── Processing screen ─── */
function ProcessingView({ stage, percent, elapsed }: { stage: string; percent: number; elapsed: number }) {
  const bucketIdx = bucketIndexOf(stage);
  const overall = overallPercentOf(stage, percent);
  const R = 68;
  const circ = 2 * Math.PI * R;
  const offset = circ * (1 - overall / 100);
  const ActiveIcon = STAGE_BUCKETS[bucketIdx].icon;

  return (
    <div className="min-h-screen bg-bg flex flex-col">
      <Navbar />
      <div className="flex-1 flex flex-col items-center justify-center px-6 pt-24 pb-16">

        {/* Circular arc */}
        <div className="relative w-44 h-44 mb-8">
          <svg className="w-full h-full -rotate-90" viewBox="0 0 160 160">
            <circle cx="80" cy="80" r={R} fill="none" stroke="rgb(var(--c-surface2))" strokeWidth="8" />
            <circle
              cx="80" cy="80" r={R} fill="none"
              stroke="rgb(var(--c-accent))" strokeWidth="8" strokeLinecap="round"
              strokeDasharray={circ}
              strokeDashoffset={offset}
              style={{ transition: "stroke-dashoffset 0.6s ease" }}
            />
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-1">
            <ActiveIcon className="w-6 h-6 text-accent-text" />
            <span className="font-mono text-2xl font-semibold text-text tabular-nums">{overall}%</span>
          </div>
        </div>

        <h2 className="font-display text-xl font-bold text-text tracking-tight mb-1 text-center">Gezi planınız hazırlanıyor</h2>
        <p className="text-text-tertiary text-xs mb-10 text-center">
          <Clock className="w-3 h-3 inline -mt-0.5 mr-1" />
          {formatElapsed(elapsed)} geçti · genellikle 2 dakikadan az sürer
        </p>

        {/* Stage list */}
        <div className="w-full max-w-xs">
          {STAGE_BUCKETS.map((b, i) => {
            const state = i < bucketIdx ? "done" : i === bucketIdx ? "active" : "pending";
            const Icon = b.icon;
            return (
              <div key={b.label} className="relative flex items-center gap-3 py-2">
                {i < STAGE_BUCKETS.length - 1 && (
                  <div className="absolute left-[15px] top-[34px] w-px h-[calc(100%-6px)] bg-border" />
                )}
                <div className={`relative z-10 w-8 h-8 rounded-full flex items-center justify-center shrink-0 border-[1.5px] transition-colors ${
                  state === "done" ? "bg-success border-success"
                  : state === "active" ? "bg-accent border-accent animate-pulse-ring"
                  : "bg-surface2 border-border-strong"
                }`}>
                  {state === "done"
                    ? <Check className="w-4 h-4 text-bg" />
                    : <Icon className={`w-3.5 h-3.5 ${state === "active" ? "text-on-accent" : "text-text-tertiary"}`} />}
                </div>
                <p className={`text-sm font-semibold ${state === "pending" ? "text-text-tertiary" : "text-text"}`}>
                  {b.label}
                </p>
              </div>
            );
          })}
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
      })
      .catch(e => {
        setTimeout(() => {
          setError(e.message);
          setLoading(false);
        }, 0);
      });
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

  if (video.status === "processing") {
    return <ProcessingView stage={progressStage} percent={progressPercent} elapsed={elapsed} />;
  }

  if (video.status === "failed") {
    return (
      <div className="min-h-screen bg-bg flex flex-col items-center justify-center gap-4">
        <AlertTriangle className="w-9 h-9 text-destructive" />
        <p className="text-text font-bold">Video işlenirken hata oluştu</p>
        <button onClick={() => router.back()} className="text-accent-text hover:underline text-sm">Geri Dön</button>
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
    <div className="min-h-screen bg-bg text-text">
      <Navbar />

      <main className="pt-24 pb-20 px-6 max-w-screen-xl mx-auto">
        <div className="flex items-center justify-between mb-8">
          <Button
            variant="ghost" size="sm"
            onClick={() => router.back()}
            className="group font-bold uppercase tracking-widest text-[10px] px-0"
          >
            <ArrowLeft className="w-4 h-4 group-hover:-translate-x-1 transition-transform" /> Geri
          </Button>
          <div className="flex items-center gap-3 no-print">
            <Button
              variant="ghost" size="sm"
              onClick={() => window.print()}
              className="rounded-full bg-surface2 border border-border-strong text-[10px] uppercase tracking-widest hover:bg-border"
              title="Tarayıcı yazdırma diyalogundan PDF olarak kaydet"
            >
              <Download className="w-3.5 h-3.5" /> PDF İndir
            </Button>
            <Link
              href={`/editor/${params.id}`}
              className="flex items-center gap-2 px-5 py-2.5 bg-accent/10 border border-accent/30 text-accent-text rounded-full text-[10px] font-black uppercase tracking-widest hover:bg-accent/20 transition-all"
            >
              <PenLine className="w-3.5 h-3.5" /> Planı Düzenle
            </Link>
            <Link
              href={`/share/${params.id}`}
              className="flex items-center gap-2 px-5 py-2.5 bg-route/10 border border-route/30 text-route rounded-full text-[10px] font-black uppercase tracking-widest hover:bg-route/20 transition-all"
            >
              <Share2 className="w-3.5 h-3.5" /> Paylaş
            </Link>
          </div>
        </div>

        {/* Header */}
        <div className="mb-8">
          <h1 className="font-display text-4xl font-black tracking-tighter mb-2 text-text">
            {locations.length > 0
              ? locations[0].original_name.charAt(0).toUpperCase() + locations[0].original_name.slice(1) + " Gezi Planı"
              : "Gezi Planı"}
          </h1>
          <div className="flex flex-wrap items-center gap-6 text-sm text-text-tertiary">
            {ai?.processing_time && <span className="flex items-center gap-1"><Clock className="w-4 h-4" /> {Math.round(ai.processing_time)}s analiz</span>}
            {video.duration      && <span className="flex items-center gap-1"><FileText className="w-4 h-4" /> {video.duration}s video</span>}
            {totalDistance       && <span className="flex items-center gap-1"><Navigation className="w-4 h-4" /> {Math.round(totalDistance)} km rota</span>}
            {ai?.detections?.count && <span className="flex items-center gap-1"><Globe2 className="w-4 h-4" /> {ai.detections.count} nesne</span>}
          </div>
        </div>

        {/* Degradation uyarısı — bazı AI aşamaları fallback'e düştüyse sonuç eksik/tahmini olabilir */}
        {video.degradation && video.degradation.successful < video.degradation.total_services && (
          <div className="mb-8 flex items-start gap-3 px-5 py-4 bg-warning/10 border border-warning/30 rounded-lg">
            <AlertTriangle className="w-4 h-4 text-warning flex-shrink-0 mt-0.5" />
            <p className="text-xs text-text-secondary leading-relaxed">
              <span className="font-black text-warning uppercase tracking-wide">Kısmi sonuç: </span>
              {video.degradation.total_services - video.degradation.successful} / {video.degradation.total_services} AI
              aşaması ({video.degradation.failed_services.join(", ")}) beklenen sonucu üretemedi, yedek değerler kullanıldı.
              Aşağıdaki bulgular eksik veya tahmini olabilir.
            </p>
          </div>
        )}

        {/* AI Pipeline İstatistikleri */}
        {ai && (
          <AIStatsCard
            processingTime={ai.processing_time ?? null}
            locationsCount={locations.length}
            detectionsCount={ai.detections?.count ?? 0}
            ocrCount={(ocrPois.length || ocrTexts.length) ?? 0}
            transcriptLength={transcript?.length ?? 0}
            tipsCount={tips.length}
            totalDistanceKm={totalDistance ?? null}
            videoDuration={video.duration}
          />
        )}

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">

          {/* Sol Panel */}
          <div className="lg:col-span-4 space-y-6">

            {locations.length > 0 && (
              <Card title="Bulunan Şehirler" icon={Building2}>
                <div className="space-y-3">
                  {locations.map((loc, i) => (
                    <div key={i} className="flex items-start gap-3">
                      <MapPin className="w-4 h-4 text-route mt-0.5 flex-shrink-0" />
                      <div>
                        <p className="font-semibold text-sm text-text">{loc.original_name.charAt(0).toUpperCase() + loc.original_name.slice(1)}</p>
                        <p className="text-xs text-text-tertiary">{loc.place_data?.name}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </Card>
            )}

            {locations.length === 0 && nerLocations.length > 0 && (
              <Card title="Tespit Edilen Yerler" icon={MapPin}>
                <div className="flex flex-wrap gap-2">
                  {nerLocations.map((loc, i) => (
                    <span key={i} className="tag">{loc}</span>
                  ))}
                </div>
              </Card>
            )}

            {tips.length > 0 && (
              <Card title="Seyahat İpuçları" icon={Lightbulb}>
                <div className="space-y-3">
                  {tips.map((tip: any, i: number) => (
                    <div key={i} className="p-3 bg-surface2 rounded-md">
                      <p className="text-xs font-bold text-accent-text mb-1">{tip.location}</p>
                      <p className="text-xs text-text-tertiary leading-relaxed">{tip.tip}</p>
                    </div>
                  ))}
                </div>
              </Card>
            )}

            {summary && (
              <Card title="Özet" icon={BookOpen}>
                <p className="text-sm text-text-tertiary leading-relaxed">{summary}</p>
              </Card>
            )}
          </div>

          {/* Sağ Panel */}
          <div className="lg:col-span-8 space-y-6">

            {locations.length > 0 && (
              <Card title="Harita" icon={Map}>
                <div className="h-[350px] rounded-md overflow-hidden">
                  <MapPreview locations={locations} />
                </div>
              </Card>
            )}

            {(ocrPois.length > 0 || ocrTexts.length > 0) && (
              <Card title="Videodaki Yazılar" icon={FileText}>
                <div className="flex flex-wrap gap-2">
                  {(ocrPois.length > 0 ? ocrPois : ocrTexts).map((text, i) => (
                    <span key={i} className="bg-surface2 border border-border text-text text-xs px-3 py-1.5 rounded-md">{text}</span>
                  ))}
                </div>
              </Card>
            )}

            {transcript && (
              <Card title="Ses Transkripsiyonu" icon={Mic}>
                <div className="flex items-start gap-3">
                  <Mic className="w-4 h-4 text-route mt-0.5 flex-shrink-0" />
                  <p className="text-sm text-text-tertiary leading-relaxed">{transcript}</p>
                </div>
              </Card>
            )}

            {locations.length === 0 && nerLocations.length === 0 && ocrTexts.length === 0 && (
              <Card title="Bilgi" icon={Info}>
                <p className="text-sm text-text-tertiary">Bu videodan lokasyon bilgisi çıkarılamadı. Türkçe yazı veya yer adı içeren videolar deneyin.</p>
              </Card>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}

function Card({ title, icon: Icon, children }: { title: string; icon: React.ComponentType<{ className?: string }>; children: React.ReactNode }) {
  return (
    <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}>
      <UICard className="p-6">
        <h3 className="flex items-center gap-2 font-display font-bold text-sm mb-4 text-text">
          <Icon className="w-4 h-4 text-text-tertiary" /> {title}
        </h3>
        {children}
      </UICard>
    </motion.div>
  );
}
