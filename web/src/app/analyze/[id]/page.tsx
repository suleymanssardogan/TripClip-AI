"use client";

import React, { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { MapPin, ArrowLeft, Clock, Mic, FileText, Loader2, Globe2, Navigation } from "lucide-react";
import Navbar from "@/components/Navbar";
import { useRouter, useParams } from "next/navigation";
import { getPlan, type VideoDetail } from "@/lib/api";
import dynamic from "next/dynamic";

const MapPreview = dynamic(() => import("@/components/MapPreview"), { ssr: false });

export default function AnalysisResultPage() {
  const router = useRouter();
  const params = useParams();
  const [video, setVideo] = useState<VideoDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const id = Number(params.id);
    if (!id || isNaN(id)) { setError("Geçersiz ID"); setLoading(false); return; }

    getPlan(id)
      .then(setVideo)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, [params.id]);

  if (loading) {
    return (
      <div className="min-h-screen bg-surface flex items-center justify-center">
        <Loader2 className="w-8 h-8 text-primary animate-spin" />
      </div>
    );
  }

  if (error || !video) {
    return (
      <div className="min-h-screen bg-surface flex flex-col items-center justify-center gap-4">
        <p className="text-red-400">{error || "Plan bulunamadı"}</p>
        <button onClick={() => router.back()} className="text-primary hover:underline text-sm">Geri Dön</button>
      </div>
    );
  }

  const ai = video.ai_results;
  const locations = ai?.nominatim?.deduplicated_locations ?? [];
  const ocrTexts = ai?.ocr?.extracted_texts ?? [];
  const nerLocations = ai?.ner?.extracted_locations ?? [];
  const ocrPois = ai?.ocr_pois ?? [];
  const transcript = ai?.audio?.transcription?.transcript;
  const tips = ai?.rag?.travel_tips?.tips ?? [];
  const summary = ai?.rag?.travel_tips?.summary;
  const totalDistance = ai?.route?.optimized_route?.total_distance_km;

  return (
    <div className="min-h-screen bg-surface text-on-surface">
      <Navbar />

      <main className="pt-24 pb-20 px-6 max-w-screen-xl mx-auto">
        <button
          onClick={() => router.back()}
          className="flex items-center gap-2 text-on-surface-variant hover:text-white transition-all mb-8 group font-bold uppercase tracking-widest text-[10px]"
        >
          <ArrowLeft className="w-4 h-4 group-hover:-translate-x-1 transition-transform" /> Geri
        </button>

        {/* Header */}
        <div className="mb-8">
          <h1 className="text-4xl font-black tracking-tighter mb-2">
            {locations.length > 0
              ? locations[0].original_name.charAt(0).toUpperCase() + locations[0].original_name.slice(1) + " Gezi Planı"
              : "Gezi Planı"}
          </h1>
          <div className="flex items-center gap-6 text-sm text-on-surface-variant">
            {ai?.processing_time && <span className="flex items-center gap-1"><Clock className="w-4 h-4" /> {Math.round(ai.processing_time)}s analiz</span>}
            {video.duration && <span className="flex items-center gap-1"><FileText className="w-4 h-4" /> {video.duration}s video</span>}
            {totalDistance && <span className="flex items-center gap-1"><Navigation className="w-4 h-4" /> {Math.round(totalDistance)} km rota</span>}
            {ai?.detections?.count && <span className="flex items-center gap-1"><Globe2 className="w-4 h-4" /> {ai.detections.count} nesne tespit</span>}
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">

          {/* Sol Panel */}
          <div className="lg:col-span-4 space-y-6">

            {/* Şehirler */}
            {locations.length > 0 && (
              <Card title="🏙️ Bulunan Şehirler">
                <div className="space-y-3">
                  {locations.map((loc, i) => (
                    <div key={i} className="flex items-start gap-3">
                      <MapPin className="w-4 h-4 text-primary mt-0.5 flex-shrink-0" />
                      <div>
                        <p className="font-semibold text-sm">{loc.original_name.charAt(0).toUpperCase() + loc.original_name.slice(1)}</p>
                        <p className="text-xs text-on-surface-variant">{loc.place_data?.name}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </Card>
            )}

            {/* NER Lokasyonlar (koordinatsız) */}
            {locations.length === 0 && nerLocations.length > 0 && (
              <Card title="📍 Tespit Edilen Yerler">
                <div className="flex flex-wrap gap-2">
                  {nerLocations.map((loc, i) => (
                    <span key={i} className="bg-primary/10 text-primary text-xs font-medium px-3 py-1 rounded-full">
                      {loc}
                    </span>
                  ))}
                </div>
              </Card>
            )}

            {/* Travel Tips */}
            {tips.length > 0 && (
              <Card title="💡 Seyahat İpuçları">
                <div className="space-y-3">
                  {tips.map((tip: any, i: number) => (
                    <div key={i} className="p-3 bg-white/5 rounded-xl">
                      <p className="text-xs font-bold text-primary mb-1">{tip.location}</p>
                      <p className="text-xs text-on-surface-variant leading-relaxed">{tip.tip}</p>
                    </div>
                  ))}
                </div>
              </Card>
            )}

            {/* Özet */}
            {summary && (
              <Card title="📖 Özet">
                <p className="text-sm text-on-surface-variant leading-relaxed">{summary}</p>
              </Card>
            )}
          </div>

          {/* Sağ Panel */}
          <div className="lg:col-span-8 space-y-6">

            {/* Harita */}
            {locations.length > 0 && (
              <Card title="🗺️ Harita">
                <div className="h-[350px] rounded-xl overflow-hidden">
                  <MapPreview locations={locations} />
                </div>
              </Card>
            )}

            {/* Videodaki Yazılar */}
            {(ocrPois.length > 0 || ocrTexts.length > 0) && (
              <Card title="📝 Videodaki Yazılar">
                <div className="flex flex-wrap gap-2">
                  {(ocrPois.length > 0 ? ocrPois : ocrTexts).map((text, i) => (
                    <span key={i} className="bg-white/5 border border-white/10 text-on-surface text-xs px-3 py-1.5 rounded-lg">
                      {text}
                    </span>
                  ))}
                </div>
              </Card>
            )}

            {/* Transkripsiyon */}
            {transcript && (
              <Card title="🎙️ Ses Transkripsiyonu">
                <div className="flex items-start gap-3">
                  <Mic className="w-4 h-4 text-primary mt-0.5 flex-shrink-0" />
                  <p className="text-sm text-on-surface-variant leading-relaxed">{transcript}</p>
                </div>
              </Card>
            )}

            {/* Veri yok */}
            {locations.length === 0 && nerLocations.length === 0 && ocrTexts.length === 0 && (
              <Card title="ℹ️ Bilgi">
                <p className="text-sm text-on-surface-variant">Bu videodan lokasyon bilgisi çıkarılamadı. Türkçe yazı veya yer adı içeren videolar deneyin.</p>
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
      className="bg-white/5 border border-white/10 rounded-2xl p-6"
    >
      <h3 className="font-bold text-sm mb-4">{title}</h3>
      {children}
    </motion.div>
  );
}
