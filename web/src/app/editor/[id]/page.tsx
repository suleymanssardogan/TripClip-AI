"use client";

import React, { useState, useEffect } from "react";
import { motion } from "framer-motion";
import {
  ChevronRight,
  Sparkles,
  Plus,
  Trash2,
  GripVertical,
  ArrowLeft,
  BrainCircuit,
} from "lucide-react";
import Navbar from "@/components/Navbar";
import { useParams, useRouter } from "next/navigation";
import { getPlan, type VideoDetail } from "@/lib/api";

/* ─── Helpers ─── */
const SLOT_TIMES  = ["09:00", "10:30", "12:00", "13:30", "15:00", "16:30", "18:00", "19:30"];
const GRAD_PAIRS: [string, string][] = [
  ["#4DFFC3", "#8B5CF6"],
  ["#8B5CF6", "#FF6B4A"],
  ["#FF6B4A", "#4DFFC3"],
  ["#3B82F6", "#4DFFC3"],
  ["#F59E0B", "#EF4444"],
  ["#10B981", "#3B82F6"],
];

function capitalize(s: string) {
  return s.charAt(0).toUpperCase() + s.slice(1);
}

function buildDays(locations: any[], tips: any[]) {
  const events = locations.map((loc, i) => {
    const tip = tips.find((t: any) =>
      t.location?.toLowerCase().includes(loc.original_name.toLowerCase()) ||
      loc.original_name.toLowerCase().includes(t.location?.toLowerCase() ?? "")
    );
    return {
      id: i + 1,
      time: SLOT_TIMES[i % SLOT_TIMES.length],
      title: capitalize(loc.original_name),
      type: loc.place_data?.type ? capitalize(loc.place_data.type) : "Gezi Noktası",
      desc: tip?.tip ?? "AI tarafından analiz edilen lokasyon.",
      grad: GRAD_PAIRS[i % GRAD_PAIRS.length],
    };
  });

  const daysCount = events.length <= 3 ? 1 : events.length <= 6 ? 2 : 3;
  const perDay    = Math.ceil(events.length / daysCount);

  return Array.from({ length: daysCount }, (_, d) => ({
    id:     String(d + 1).padStart(2, "0"),
    label:  `Gün ${d + 1}`,
    events: events.slice(d * perDay, (d + 1) * perDay),
  }));
}

/* ─── Main ─── */
export default function EditorPage() {
  const params = useParams();
  const router = useRouter();
  const [video,    setVideo]    = useState<VideoDetail | null>(null);
  const [loading,  setLoading]  = useState(true);
  const [error,    setError]    = useState("");
  const [activeDay, setActiveDay] = useState(0);

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

  const ai        = video.ai_results;
  const locations = ai?.nominatim?.deduplicated_locations ?? [];
  const tips      = ai?.rag?.travel_tips?.tips ?? [];
  const summary   = ai?.rag?.travel_tips?.summary;
  const days      = buildDays(locations, tips);
  const title     = locations.length > 0
    ? `${capitalize(locations[0].original_name)} Gezi Planı`
    : video.filename.replace(/\.[^.]+$/, "");

  /* Empty state */
  if (locations.length === 0) {
    return (
      <div className="min-h-screen bg-surface text-ice">
        <Navbar />
        <div className="pt-32 pb-20 px-6 max-w-screen-xl mx-auto flex flex-col items-center justify-center gap-6 text-center">
          <p className="text-5xl">🗺️</p>
          <h2 className="text-2xl font-black tracking-tight">Lokasyon bulunamadı</h2>
          <p className="text-muted text-sm max-w-sm">Bu videodan konum bilgisi çıkarılamadı. Lütfen başka bir video deneyin.</p>
          <button onClick={() => router.back()} className="text-neon hover:underline text-sm">Geri Dön</button>
        </div>
      </div>
    );
  }

  const activeEvents = days[activeDay]?.events ?? [];

  return (
    <div className="min-h-screen bg-surface font-sans text-ice">
      <Navbar />

      <main className="max-w-screen-2xl mx-auto px-6 py-12 flex flex-col lg:flex-row gap-12 pt-32">

        {/* ── Left Sidebar ── */}
        <aside className="w-full lg:w-80 flex-shrink-0 flex flex-col gap-8">

          <div className="space-y-4">
            <button
              onClick={() => router.back()}
              className="flex items-center gap-2 text-muted hover:text-ice transition-all text-[10px] font-black uppercase tracking-widest"
            >
              <ArrowLeft className="w-3 h-3" /> Geri
            </button>
            <span className="text-neon font-display text-xs font-black uppercase tracking-[0.3em]">Gezi Editörü</span>
            <h2 className="text-4xl font-black text-ice font-display tracking-tighter leading-none">{title}</h2>
            {summary && (
              <p className="text-muted text-sm leading-relaxed font-medium">{summary}</p>
            )}
          </div>

          {/* Day tabs */}
          <div className="flex flex-col gap-3">
            {days.map((day, i) => (
              <button
                key={day.id}
                onClick={() => setActiveDay(i)}
                className={`flex items-center justify-between p-5 rounded-2xl transition-all ${
                  activeDay === i
                    ? "bg-neon/10 border-l-4 border-neon text-neon"
                    : "bg-white/5 hover:bg-white/10 text-muted"
                }`}
              >
                <div className="flex flex-col items-start">
                  <span className="text-[10px] uppercase tracking-widest font-black opacity-60">{day.label}</span>
                  <span className="font-black text-sm uppercase">{day.id}: {day.events[0]?.title ?? "—"}</span>
                </div>
                <ChevronRight className="w-4 h-4" />
              </button>
            ))}
          </div>

          {/* AI Optimizer widget */}
          <div className="neon-card p-8 rounded-[2.5rem] relative overflow-hidden shadow-2xl">
            <div className="absolute top-0 right-0 p-6 opacity-5">
              <BrainCircuit className="w-16 h-16 text-neon" />
            </div>
            <div className="relative z-10">
              <h4 className="font-display font-black text-neon flex items-center gap-2 mb-4 tracking-tight">
                <Sparkles className="w-5 h-5" />
                AI Optimizer
              </h4>
              <p className="text-xs text-muted leading-relaxed font-bold mb-6">
                {tips.length > 0
                  ? tips[0].tip
                  : "AI rota optimizasyonu tamamlandı. Lokasyonlar en verimli sırayla düzenlendi."}
              </p>
              <button className="text-[10px] font-black uppercase tracking-[0.2em] text-neon border-b-2 border-neon/20 pb-1">
                Detayları Gör
              </button>
            </div>
          </div>
        </aside>

        {/* ── Timeline ── */}
        <section className="flex-grow">
          <div className="flex items-center justify-between mb-12">
            <div className="flex items-center gap-6">
              <div className="px-6 py-2 bg-neon text-surface rounded-full text-[10px] font-black uppercase tracking-[0.2em]">Editing Mode</div>
              <span className="text-xs text-muted font-bold italic opacity-40">{activeEvents.length} durak · {days[activeDay]?.label}</span>
            </div>
            <button className="bg-violet text-white px-8 py-4 rounded-full text-xs font-black uppercase tracking-[0.2em] flex items-center gap-2 hover:scale-[1.02] active:scale-95 transition-all shadow-violet">
              <Plus className="w-4 h-4" />
              Add Stop
            </button>
          </div>

          <div className="relative space-y-12">
            <div className="absolute left-[22px] top-4 bottom-4 w-px bg-white/10 hidden lg:block" />

            {activeEvents.map((event, i) => (
              <motion.div
                key={event.id}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.08 }}
                className="relative flex flex-col lg:flex-row gap-8 items-start group"
              >
                <div className={`absolute left-[14px] w-4 h-4 rounded-full border-4 border-surface z-10 hidden lg:block mt-8 transition-colors ${i === 0 ? "bg-neon" : "bg-violet"}`} />

                <div className="neon-card rounded-[3rem] shadow-2xl overflow-hidden flex flex-col lg:flex-row w-full">

                  {/* Gradient placeholder (replaces photo) */}
                  <div
                    className="w-full lg:w-64 h-64 lg:h-auto relative flex-shrink-0"
                    style={{ background: `linear-gradient(135deg, ${event.grad[0]}, ${event.grad[1]})` }}
                  >
                    <div className="absolute top-6 left-6 bg-surface/90 backdrop-blur px-4 py-2 rounded-2xl text-[10px] font-black uppercase tracking-widest shadow-2xl text-ice">
                      {event.time}
                    </div>
                    <div className="absolute bottom-6 left-6 right-6">
                      <p className="text-surface/80 text-xs font-black uppercase tracking-widest">{event.type}</p>
                    </div>
                  </div>

                  {/* Content */}
                  <div className="p-10 flex-grow flex flex-col">
                    <div className="flex justify-between items-start mb-6">
                      <div>
                        <h3 className="text-3xl font-black font-display text-ice tracking-tighter leading-none mb-3">{event.title}</h3>
                        <p className="text-neon font-black text-xs uppercase tracking-[0.2em]">{event.type}</p>
                      </div>
                      {/* Optimize toggle */}
                      <div className="flex items-center gap-3 bg-black/20 p-2 rounded-full px-4">
                        <div className="w-8 h-4 bg-white/10 rounded-full relative p-1 cursor-pointer">
                          <div className={`w-2 h-2 rounded-full transition-all ${i === 0 ? "translate-x-4 bg-neon" : "bg-muted"}`} />
                        </div>
                        <span className="text-[10px] font-black text-muted uppercase tracking-[0.2em] hidden sm:inline">Optimize</span>
                      </div>
                    </div>

                    <p className="text-muted text-sm font-medium leading-relaxed max-w-lg mb-8">{event.desc}</p>

                    <div className="mt-auto pt-8 border-t border-white/5 flex items-center justify-between">
                      <div className="flex -space-x-3">
                        <div className="w-10 h-10 rounded-full border-4 border-card bg-neon text-surface flex items-center justify-center text-[10px] font-black shadow-xl">AI</div>
                        <div className="w-10 h-10 rounded-full border-4 border-card bg-violet text-white flex items-center justify-center text-[10px] font-black shadow-xl">IG</div>
                      </div>
                      <div className="flex gap-4">
                        <button className="text-muted hover:text-ice transition-colors"><GripVertical className="w-5 h-5" /></button>
                        <button className="text-muted hover:text-coral transition-colors"><Trash2 className="w-5 h-5" /></button>
                      </div>
                    </div>
                  </div>
                </div>
              </motion.div>
            ))}
          </div>
        </section>
      </main>
    </div>
  );
}
