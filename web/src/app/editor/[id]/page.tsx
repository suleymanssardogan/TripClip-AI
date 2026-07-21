"use client";

import React, { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  ChevronRight,
  Sparkles,
  ArrowLeft,
  Save,
  RotateCcw,
  MapPin,
  Check,
} from "lucide-react";
import Navbar from "@/components/Navbar";
import { useParams, useRouter } from "next/navigation";
import { getPlan, type VideoDetail } from "@/lib/api";

interface Event {
  id: number;
  time: string;
  title: string;
  type: string;
  desc: string;
}

/* ─── Helpers ─── */
const SLOT_TIMES = ["09:00", "10:30", "12:00", "13:30", "15:00", "16:30", "18:00", "19:30"];

function capitalize(s: string) {
  return s.charAt(0).toUpperCase() + s.slice(1);
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function buildDays(locations: any[], tips: any[]) {
  const events: Event[] = locations.map((loc, i) => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
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

  // Reorder edilebilir gün-bazlı event listesi
  const [dayEvents, setDayEvents]     = useState<Event[][]>([]);
  const [dirty, setDirty]             = useState(false);
  const [savedToast, setSavedToast]   = useState(false);
  const dragIndex   = useRef<number | null>(null);
  const [overIndex, setOverIndex]     = useState<number | null>(null);

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

  // Video geldiğinde, dayEvents'i baştan kur (veya localStorage'dan oku)
  useEffect(() => {
    if (!video) return;
    const ai = video.ai_results;
    const locations = ai?.nominatim?.deduplicated_locations ?? [];
    const tips      = ai?.rag?.travel_tips?.tips ?? [];
    const built     = buildDays(locations, tips).map(d => d.events);

    // localStorage'da kullanıcının önceki sıralaması varsa onu yükle
    const saved = typeof window !== "undefined"
      ? localStorage.getItem(`editor-order-${video.id}`)
      : null;
    if (saved) {
      try {
        const parsed: number[][] = JSON.parse(saved);
        // ID listelerine göre yeniden sırala
        const flat = built.flat();
        const reordered = parsed.map(ids =>
          ids.map(id => flat.find(e => e.id === id)).filter(Boolean) as Event[]
        );
        if (reordered.flat().length === flat.length) {
          setTimeout(() => {
            setDayEvents(reordered);
          }, 0);
          return;
        }
      } catch { /* parse hatası — varsayılan kullan */ }
    }
    setTimeout(() => {
      setDayEvents(built);
    }, 0);
  }, [video]);

  // ── Drag handlers ──
  function handleDragStart(idx: number) {
    dragIndex.current = idx;
  }
  function handleDragOver(e: React.DragEvent, idx: number) {
    e.preventDefault();
    if (overIndex !== idx) setOverIndex(idx);
  }
  function handleDrop(targetIdx: number) {
    const from = dragIndex.current;
    setOverIndex(null);
    dragIndex.current = null;
    if (from === null || from === targetIdx) return;

    setDayEvents(prev => {
      const copy = prev.map(arr => [...arr]);
      const list = copy[activeDay];
      const [moved] = list.splice(from, 1);
      list.splice(targetIdx, 0, moved);
      // Slot zamanlarını yeni sıraya göre güncelle
      copy[activeDay] = list.map((e, i) => ({ ...e, time: SLOT_TIMES[i % SLOT_TIMES.length] }));
      return copy;
    });
    setDirty(true);
  }
  function handleDragEnd() {
    setOverIndex(null);
    dragIndex.current = null;
  }

  // Sıralamayı kaydet
  function persistOrder() {
    if (!video) return;
    const ids = dayEvents.map(arr => arr.map(e => e.id));
    localStorage.setItem(`editor-order-${video.id}`, JSON.stringify(ids));
    setDirty(false);
    setSavedToast(true);
    setTimeout(() => setSavedToast(false), 2200);
  }

  function resetOrder() {
    if (!video) return;
    localStorage.removeItem(`editor-order-${video.id}`);
    const ai = video.ai_results;
    const locations = ai?.nominatim?.deduplicated_locations ?? [];
    const tips      = ai?.rag?.travel_tips?.tips ?? [];
    setDayEvents(buildDays(locations, tips).map(d => d.events));
    setDirty(false);
  }

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

  const ai        = video.ai_results;
  const locations = ai?.nominatim?.deduplicated_locations ?? [];
  const tips      = ai?.rag?.travel_tips?.tips ?? [];
  const summary   = ai?.rag?.travel_tips?.summary;
  // Günleri stateful events'ten türet (drag-drop'dan sonra güncel kalır)
  const days = dayEvents.length
    ? dayEvents.map((events, d) => ({
        id:     String(d + 1).padStart(2, "0"),
        label:  `Gün ${d + 1}`,
        events,
      }))
    : buildDays(locations, tips);
  const title     = locations.length > 0
    ? `${capitalize(locations[0].original_name)} Gezi Planı`
    : video.filename.replace(/\.[^.]+$/, "");

  /* Empty state */
  if (locations.length === 0) {
    return (
      <div className="min-h-screen bg-bg text-text">
        <Navbar />
        <div className="pt-32 pb-20 px-6 max-w-screen-xl mx-auto flex flex-col items-center justify-center gap-4 text-center">
          <MapPin className="w-10 h-10 text-text-tertiary" />
          <h2 className="font-display text-2xl font-black tracking-tight text-text">Lokasyon bulunamadı</h2>
          <p className="text-text-secondary text-sm max-w-sm">Bu videodan konum bilgisi çıkarılamadı. Lütfen başka bir video deneyin.</p>
          <button onClick={() => router.back()} className="text-accent-text hover:underline text-sm">Geri Dön</button>
        </div>
      </div>
    );
  }

  const activeEvents = days[activeDay]?.events ?? [];

  return (
    <div className="min-h-screen bg-bg font-sans text-text">
      <Navbar />

      <main className="max-w-screen-2xl mx-auto px-6 py-12 flex flex-col lg:flex-row gap-12 pt-32">

        {/* ── Left Sidebar ── */}
        <aside className="w-full lg:w-80 flex-shrink-0 flex flex-col gap-8">

          <div className="space-y-4">
            <button
              onClick={() => router.back()}
              className="flex items-center gap-2 text-text-tertiary hover:text-text transition-all text-[10px] font-black uppercase tracking-widest"
            >
              <ArrowLeft className="w-3 h-3" /> Geri
            </button>
            <span className="text-accent-text font-display text-xs font-black uppercase tracking-[0.3em]">Gezi Editörü</span>
            <h2 className="font-display text-4xl font-black text-text tracking-tighter leading-none">{title}</h2>
            {summary && (
              <p className="text-text-secondary text-sm leading-relaxed">{summary}</p>
            )}
          </div>

          {/* Day tabs */}
          <div className="flex flex-col gap-3">
            {days.map((day, i) => (
              <button
                key={day.id}
                onClick={() => setActiveDay(i)}
                className={`flex items-center justify-between p-5 rounded-md transition-all ${
                  activeDay === i
                    ? "bg-accent/10 border-l-4 border-accent text-accent-text"
                    : "bg-surface hover:bg-surface2 border-l-4 border-transparent text-text-secondary"
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

          {/* AI özet widget */}
          <div className="bg-surface border border-border p-8 rounded-lg relative overflow-hidden">
            <div className="relative z-10">
              <h4 className="font-display font-black text-accent-text flex items-center gap-2 mb-4 tracking-tight">
                <Sparkles className="w-5 h-5" />
                AI Notu
              </h4>
              <p className="text-xs text-text-secondary leading-relaxed">
                {tips.length > 0
                  ? tips[0].tip
                  : "Rota optimizasyonu tamamlandı. Lokasyonlar en verimli sırayla düzenlendi."}
              </p>
            </div>
          </div>
        </aside>

        {/* ── Timeline ── */}
        <section className="flex-grow">
          <div className="relative flex flex-wrap items-center justify-between mb-12 gap-3">
            <div className="flex items-center gap-6">
              <div className="px-6 py-2 bg-accent text-on-accent rounded-full text-[10px] font-black uppercase tracking-[0.2em]">Düzenleme Modu</div>
              <span className="text-xs text-text-tertiary font-medium">
                {activeEvents.length} durak · {days[activeDay]?.label} · sürükleyerek sırala
              </span>
            </div>
            <div className="flex items-center gap-2">
              {dirty && (
                <button
                  onClick={resetOrder}
                  className="flex items-center gap-2 px-4 py-3 bg-surface hover:bg-surface2 border border-border-strong text-text-secondary rounded-full text-[10px] font-black uppercase tracking-[0.2em] transition-all"
                >
                  <RotateCcw className="w-3.5 h-3.5" /> Sıfırla
                </button>
              )}
              <button
                onClick={persistOrder}
                disabled={!dirty}
                className={`flex items-center gap-2 px-6 py-3 rounded-full text-[10px] font-black uppercase tracking-[0.2em] transition-all ${
                  dirty
                    ? "bg-accent text-on-accent hover:bg-accent-hover"
                    : "bg-surface2 text-text-tertiary cursor-not-allowed"
                }`}
              >
                <Save className="w-3.5 h-3.5" /> Kaydet
              </button>
            </div>
            <AnimatePresence>
              {savedToast && (
                <motion.div
                  initial={{ opacity: 0, y: -8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -8 }}
                  className="fixed top-20 right-6 z-50 flex items-center gap-2 bg-success text-bg px-5 py-3 rounded-full text-[10px] font-black uppercase tracking-widest"
                >
                  <Check className="w-3.5 h-3.5" /> Sıralama kaydedildi
                </motion.div>
              )}
            </AnimatePresence>
          </div>

          <div className="relative space-y-8">
            <div className="absolute left-[22px] top-4 bottom-4 w-px bg-border hidden lg:block" />

            {activeEvents.map((event, i) => (
              <motion.div
                key={event.id}
                layout
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.06, layout: { duration: 0.3 } }}
                onDragOver={(e) => handleDragOver(e, i)}
                onDrop={() => handleDrop(i)}
                onDragEnd={handleDragEnd}
                className={`relative flex flex-col lg:flex-row gap-8 items-start ${
                  overIndex === i ? "ring-2 ring-accent/40 ring-offset-4 ring-offset-bg rounded-lg" : ""
                }`}
              >
                <div className="absolute left-[14px] w-4 h-4 rounded-full border-4 border-bg bg-route z-10 hidden lg:block mt-8" />

                <div
                  draggable
                  onDragStart={() => handleDragStart(i)}
                  className="bg-surface border border-border rounded-lg overflow-hidden flex flex-col lg:flex-row w-full cursor-grab active:cursor-grabbing hover:border-border-strong transition-colors">

                  {/* Konum ikonu (fotoğraf yerine) */}
                  <div className="w-full lg:w-52 h-40 lg:h-auto relative flex-shrink-0 bg-surface2 flex items-center justify-center">
                    <MapPin className="w-8 h-8 text-text-tertiary" />
                    <div className="absolute top-4 left-4 bg-bg/90 backdrop-blur px-3 py-1.5 rounded-full font-mono text-[10px] font-semibold uppercase tracking-widest text-text">
                      {event.time}
                    </div>
                  </div>

                  {/* Content */}
                  <div className="p-8 flex-grow flex flex-col">
                    <div className="mb-4">
                      <h3 className="font-display text-2xl font-black text-text tracking-tight leading-tight mb-1">{event.title}</h3>
                      <p className="text-route font-bold text-xs uppercase tracking-[0.2em]">{event.type}</p>
                    </div>

                    <p className="text-text-secondary text-sm leading-relaxed max-w-lg mb-6">{event.desc}</p>

                    <div className="mt-auto pt-6 border-t border-border flex items-center justify-between">
                      <span className="font-mono text-[10px] text-text-tertiary uppercase tracking-widest">AI tarafından tespit edildi</span>
                      <div className="w-9 h-9 rounded-full bg-accent/10 border border-accent/25 text-accent-text flex items-center justify-center text-[10px] font-black">AI</div>
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
