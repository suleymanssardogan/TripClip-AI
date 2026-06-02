"use client";

import { motion } from "framer-motion";
import {
  Cpu, MapPin, Eye, FileSearch, Mic, Lightbulb, Navigation, Timer,
} from "lucide-react";
import type { ReactNode } from "react";

interface Props {
  processingTime: number | null;     // saniye
  locationsCount: number;
  detectionsCount: number;
  ocrCount: number;
  transcriptLength: number;          // karakter
  tipsCount: number;
  totalDistanceKm: number | null;
  videoDuration: number | null;
}

interface Stat {
  icon: ReactNode;
  label: string;
  value: string;
  hint?: string;
  color: string;
}

export default function AIStatsCard(p: Props) {
  const stats: Stat[] = [
    {
      icon: <Cpu className="w-5 h-5" />,
      label: "İşlem Süresi",
      value: p.processingTime ? `${Math.round(p.processingTime)}s` : "—",
      hint: p.processingTime && p.videoDuration
        ? `${(p.processingTime / p.videoDuration).toFixed(1)}x video`
        : undefined,
      color: "neon",
    },
    {
      icon: <MapPin className="w-5 h-5" />,
      label: "Lokasyon",
      value: String(p.locationsCount),
      hint: "tespit edildi",
      color: "violet",
    },
    {
      icon: <Eye className="w-5 h-5" />,
      label: "Görsel Nesne",
      value: String(p.detectionsCount),
      hint: "YOLOv8 tarafından",
      color: "coral",
    },
    {
      icon: <FileSearch className="w-5 h-5" />,
      label: "OCR Yazı",
      value: String(p.ocrCount),
      hint: "tabela / yazı",
      color: "neon",
    },
    {
      icon: <Mic className="w-5 h-5" />,
      label: "Transkript",
      value: p.transcriptLength > 0 ? `${p.transcriptLength}` : "—",
      hint: "karakter",
      color: "violet",
    },
    {
      icon: <Lightbulb className="w-5 h-5" />,
      label: "AI İpucu",
      value: String(p.tipsCount),
      hint: "RAG sistemi",
      color: "coral",
    },
    {
      icon: <Navigation className="w-5 h-5" />,
      label: "Toplam Rota",
      value: p.totalDistanceKm ? `${Math.round(p.totalDistanceKm)} km` : "—",
      hint: "TSP optimize",
      color: "neon",
    },
    {
      icon: <Timer className="w-5 h-5" />,
      label: "Video",
      value: p.videoDuration ? `${p.videoDuration}s` : "—",
      hint: "süresi",
      color: "violet",
    },
  ];

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
      className="neon-card rounded-2xl p-6 mb-8"
    >
      {/* Başlık */}
      <div className="flex items-center justify-between mb-5">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-neon/10 border border-neon/25 flex items-center justify-center">
            <Cpu className="w-4 h-4 text-neon" />
          </div>
          <div>
            <h3 className="font-black text-sm text-ice tracking-tight">AI Pipeline İstatistikleri</h3>
            <p className="text-[10px] text-muted uppercase tracking-widest mt-0.5">
              7 ML modeli · paralel işleme
            </p>
          </div>
        </div>
        <span className="px-3 py-1 rounded-full bg-neon/10 border border-neon/25 text-neon text-[9px] font-black uppercase tracking-widest">
          Live
        </span>
      </div>

      {/* Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {stats.map((s, i) => (
          <motion.div
            key={s.label}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.04 }}
            className="bg-white/[0.03] border border-white/5 rounded-xl p-3 hover:border-white/15 transition-colors"
          >
            <div className={`text-${s.color} mb-2 opacity-90`}>{s.icon}</div>
            <p className="text-2xl font-black text-ice leading-none mb-1.5 tabular-nums">
              {s.value}
            </p>
            <p className="text-[10px] text-muted uppercase tracking-wider font-bold">
              {s.label}
            </p>
            {s.hint && (
              <p className="text-[9px] text-muted/70 mt-1">{s.hint}</p>
            )}
          </motion.div>
        ))}
      </div>
    </motion.div>
  );
}
