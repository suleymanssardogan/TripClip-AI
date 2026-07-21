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
    },
    {
      icon: <MapPin className="w-5 h-5" />,
      label: "Lokasyon",
      value: String(p.locationsCount),
      hint: "tespit edildi",
    },
    {
      icon: <Eye className="w-5 h-5" />,
      label: "Görsel Nesne",
      value: String(p.detectionsCount),
      hint: "YOLOv8 tarafından",
    },
    {
      icon: <FileSearch className="w-5 h-5" />,
      label: "OCR Yazı",
      value: String(p.ocrCount),
      hint: "tabela / yazı",
    },
    {
      icon: <Mic className="w-5 h-5" />,
      label: "Transkript",
      value: p.transcriptLength > 0 ? `${p.transcriptLength}` : "—",
      hint: "karakter",
    },
    {
      icon: <Lightbulb className="w-5 h-5" />,
      label: "AI İpucu",
      value: String(p.tipsCount),
      hint: "RAG sistemi",
    },
    {
      icon: <Navigation className="w-5 h-5" />,
      label: "Toplam Rota",
      value: p.totalDistanceKm ? `${Math.round(p.totalDistanceKm)} km` : "—",
      hint: "TSP optimize",
    },
    {
      icon: <Timer className="w-5 h-5" />,
      label: "Video",
      value: p.videoDuration ? `${p.videoDuration}s` : "—",
      hint: "süresi",
    },
  ];

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
      className="bg-surface border border-border rounded-lg p-6 mb-8"
    >
      {/* Başlık */}
      <div className="flex items-center justify-between mb-5">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-md bg-accent/10 border border-accent/25 flex items-center justify-center">
            <Cpu className="w-4 h-4 text-accent-text" />
          </div>
          <div>
            <h3 className="font-display font-bold text-sm text-text tracking-tight">AI Pipeline İstatistikleri</h3>
            <p className="font-mono text-[10px] text-text-tertiary uppercase tracking-widest mt-0.5">
              7 ML modeli · paralel işleme
            </p>
          </div>
        </div>
        <span className="px-3 py-1 rounded-full bg-route/10 border border-route/25 text-route font-mono text-[9px] font-bold uppercase tracking-widest">
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
            className="bg-surface2 border border-border rounded-md p-3 hover:border-border-strong transition-colors"
          >
            <div className="text-text-tertiary mb-2">{s.icon}</div>
            <p className="font-mono text-2xl font-semibold text-text leading-none mb-1.5 tabular-nums">
              {s.value}
            </p>
            <p className="text-[10px] text-text-secondary uppercase tracking-wider font-semibold">
              {s.label}
            </p>
            {s.hint && (
              <p className="text-[9px] text-text-tertiary mt-1">{s.hint}</p>
            )}
          </motion.div>
        ))}
      </div>
    </motion.div>
  );
}
