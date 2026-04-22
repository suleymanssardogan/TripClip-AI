"use client";

import React, { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Search, MapPin, Clock, Sparkles, TrendingUp,
  ArrowRight, Filter, Globe, RotateCcw
} from "lucide-react";
import Navbar from "@/components/Navbar";
import Link from "next/link";
import { getPlans, getStats, Plan, PlatformStats } from "@/lib/api";

const CITY_FILTERS = [
  "Tümü", "İstanbul", "Ankara", "İzmir", "Antalya",
  "Gaziantep", "Kapadokya", "Trabzon", "Bodrum", "Mardin"
];

function PlanCard({ plan, index }: { plan: Plan; index: number }) {
  const city = plan.top_location ?? "Türkiye";
  const duration = plan.duration ? `${Math.round(plan.duration)}s` : "—";
  const createdAt = new Date(plan.created_at).toLocaleDateString("tr-TR", {
    day: "numeric", month: "short"
  });

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.05 }}
    >
      <Link href={`/analyze/${plan.id}`} className="block group">
        <div className="neon-card rounded-2xl overflow-hidden h-full">
          {/* Renk banner — thumbnail yoksa gradient */}
          <div className={`h-36 relative flex items-end p-4 ${gradientForId(plan.id)}`}>
            <div className="absolute inset-0 bg-gradient-to-t from-black/70 to-transparent" />
            <div className="relative z-10">
              <span className="tag text-[10px]">
                {plan.locations_count} Mekan
              </span>
            </div>
            <div className="absolute top-3 right-3">
              <div className="w-2 h-2 rounded-full bg-neon animate-pulse" />
            </div>
          </div>

          {/* İçerik */}
          <div className="p-4">
            <div className="flex items-center gap-1.5 text-neon text-xs font-medium mb-2">
              <MapPin className="w-3 h-3" />
              {city}
            </div>

            <h3 className="text-ice font-semibold text-sm leading-snug mb-3 line-clamp-2 group-hover:text-neon transition-colors">
              {plan.filename.replace(/\.[^.]+$/, "").replace(/[-_]/g, " ")}
            </h3>

            {/* OCR preview tags */}
            {plan.ocr_preview.length > 0 && (
              <div className="flex flex-wrap gap-1 mb-3">
                {plan.ocr_preview.slice(0, 3).map((t, i) => (
                  <span key={i} className="text-[10px] text-muted bg-white/5 px-2 py-0.5 rounded-full">
                    {t}
                  </span>
                ))}
              </div>
            )}

            <div className="flex items-center justify-between text-xs text-muted mt-auto pt-2 border-t border-white/5">
              <span className="flex items-center gap-1">
                <Clock className="w-3 h-3" /> {duration}
              </span>
              <span>{createdAt}</span>
            </div>
          </div>
        </div>
      </Link>
    </motion.div>
  );
}

function gradientForId(id: number): string {
  const gradients = [
    "bg-gradient-to-br from-neon/30 to-violet/20",
    "bg-gradient-to-br from-violet/30 to-coral/20",
    "bg-gradient-to-br from-coral/30 to-neon/20",
    "bg-gradient-to-br from-blue-500/30 to-neon/20",
    "bg-gradient-to-br from-amber-500/30 to-coral/20",
  ];
  return gradients[id % gradients.length];
}

export default function ExplorePage() {
  const [plans, setPlans]       = useState<Plan[]>([]);
  const [stats, setStats]       = useState<PlatformStats | null>(null);
  const [loading, setLoading]   = useState(true);
  const [search, setSearch]     = useState("");
  const [city, setCity]         = useState("Tümü");
  const [offset, setOffset]     = useState(0);
  const [total, setTotal]       = useState(0);
  const LIMIT = 12;

  const fetchPlans = useCallback(async (cityFilter: string, off: number) => {
    setLoading(true);
    try {
      const params: { city?: string; limit: number; offset: number } = {
        limit: LIMIT, offset: off
      };
      if (cityFilter !== "Tümü") params.city = cityFilter;
      const res = await getPlans(params);
      setPlans(res.plans);
      setTotal(res.total);
    } catch {
      setPlans([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchPlans(city, 0);
    getStats().then(setStats).catch(() => {});
  }, [city, fetchPlans]);

  const filtered = plans.filter(p =>
    search === "" ||
    p.filename.toLowerCase().includes(search.toLowerCase()) ||
    (p.top_location ?? "").toLowerCase().includes(search.toLowerCase()) ||
    p.ocr_preview.some(t => t.toLowerCase().includes(search.toLowerCase()))
  );

  return (
    <div className="min-h-screen bg-bg">
      <Navbar />

      {/* Hero */}
      <section className="relative pt-28 pb-16 px-6 overflow-hidden">
        <div className="absolute inset-0 pointer-events-none">
          <div className="orb w-[500px] h-[500px] bg-neon -top-40 -left-40" />
          <div className="orb w-[400px] h-[400px] bg-violet top-0 -right-32" />
        </div>

        <div className="relative max-w-4xl mx-auto text-center">
          <div className="inline-flex items-center gap-2 bg-neon/10 border border-neon/20 rounded-full px-4 py-1.5 text-neon text-xs font-mono mb-6">
            <Globe className="w-3 h-3" />
            {stats ? `${stats.total_cities}+ şehir keşfedildi` : "Keşfet"}
          </div>

          <h1 className="font-display font-black text-4xl md:text-6xl text-ice mb-4 leading-tight">
            Gerçek Seyahat<br />
            <span className="text-neon">Deneyimleri</span>
          </h1>
          <p className="text-muted text-lg mb-10">
            AI'ın analiz ettiği videolardan çıkarılan gerçek mekanlar ve rotalar
          </p>

          {/* Arama kutusu */}
          <div className="relative max-w-xl mx-auto">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-muted" />
            <input
              type="text"
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Şehir, mekan veya tabela ara..."
              className="w-full bg-white/5 border border-white/10 rounded-xl pl-11 pr-4 py-3.5 text-ice placeholder:text-muted/50 text-sm focus:outline-none focus:border-neon/40 transition-all"
            />
          </div>
        </div>
      </section>

      {/* Stats bar */}
      {stats && (
        <div className="border-y border-white/5 bg-white/2 py-4 px-6">
          <div className="max-w-7xl mx-auto flex items-center justify-center gap-10 text-sm">
            {[
              { label: "Analiz Edilen Video", value: stats.completed_videos },
              { label: "Keşfedilen Şehir", value: stats.total_cities },
              { label: "Kayıtlı Kullanıcı", value: stats.total_users },
            ].map(s => (
              <div key={s.label} className="text-center">
                <div className="font-display font-black text-xl text-neon">{s.value}</div>
                <div className="text-muted text-xs">{s.label}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Şehir filtreleri */}
      <div className="sticky top-16 z-40 bg-bg/90 backdrop-blur-xl border-b border-white/5 px-6 py-3">
        <div className="max-w-7xl mx-auto flex items-center gap-2 overflow-x-auto no-scrollbar">
          <Filter className="w-4 h-4 text-muted flex-shrink-0" />
          {CITY_FILTERS.map(c => (
            <button
              key={c}
              onClick={() => { setCity(c); setOffset(0); }}
              className={`flex-shrink-0 px-4 py-1.5 rounded-full text-xs font-medium transition-all ${
                city === c
                  ? "bg-neon text-bg font-bold"
                  : "bg-white/5 text-muted hover:text-ice hover:bg-white/10"
              }`}
            >
              {c}
            </button>
          ))}
        </div>
      </div>

      {/* Grid */}
      <main className="max-w-7xl mx-auto px-6 py-10">
        {loading ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-5">
            {Array.from({ length: 8 }).map((_, i) => (
              <div key={i} className="h-64 rounded-2xl bg-white/5 animate-pulse" />
            ))}
          </div>
        ) : filtered.length === 0 ? (
          <div className="text-center py-24">
            <div className="text-5xl mb-4">🗺️</div>
            <p className="text-ice font-semibold mb-2">
              {total === 0 ? "Henüz analiz edilmiş video yok" : "Sonuç bulunamadı"}
            </p>
            <p className="text-muted text-sm mb-6">
              {total === 0
                ? "iOS uygulamasından ilk videoyu yükle!"
                : "Farklı bir şehir veya arama dene"}
            </p>
            {search && (
              <button
                onClick={() => setSearch("")}
                className="btn-neon px-4 py-2 rounded-lg text-sm flex items-center gap-2 mx-auto"
              >
                <RotateCcw className="w-3 h-3" /> Temizle
              </button>
            )}
          </div>
        ) : (
          <>
            <div className="flex items-center justify-between mb-6">
              <p className="text-muted text-sm">
                <span className="text-ice font-semibold">{total}</span> gezi analizi
                {city !== "Tümü" && <span> · {city}</span>}
              </p>
              <div className="flex items-center gap-1 text-xs text-muted">
                <TrendingUp className="w-3 h-3" /> En yeni önce
              </div>
            </div>

            <AnimatePresence mode="wait">
              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-5">
                {filtered.map((plan, i) => (
                  <PlanCard key={plan.id} plan={plan} index={i} />
                ))}
              </div>
            </AnimatePresence>

            {/* Pagination */}
            {total > LIMIT && (
              <div className="flex items-center justify-center gap-3 mt-12">
                <button
                  onClick={() => { const o = Math.max(0, offset - LIMIT); setOffset(o); fetchPlans(city, o); }}
                  disabled={offset === 0}
                  className="px-5 py-2 rounded-lg bg-white/5 text-sm text-muted hover:text-ice disabled:opacity-30 transition-all"
                >
                  ← Önceki
                </button>
                <span className="text-muted text-sm">
                  {Math.floor(offset / LIMIT) + 1} / {Math.ceil(total / LIMIT)}
                </span>
                <button
                  onClick={() => { const o = offset + LIMIT; setOffset(o); fetchPlans(city, o); }}
                  disabled={offset + LIMIT >= total}
                  className="px-5 py-2 rounded-lg bg-white/5 text-sm text-muted hover:text-ice disabled:opacity-30 transition-all flex items-center gap-1"
                >
                  Sonraki <ArrowRight className="w-3 h-3" />
                </button>
              </div>
            )}
          </>
        )}

        {/* CTA */}
        <div className="mt-20 animated-border rounded-2xl">
          <div className="bg-bg rounded-2xl p-10 text-center">
            <Sparkles className="w-8 h-8 text-neon mx-auto mb-4" />
            <h3 className="font-display font-black text-2xl text-ice mb-2">
              Kendi Rotanı Oluştur
            </h3>
            <p className="text-muted mb-6 text-sm max-w-md mx-auto">
              Instagram videolarından AI ile otomatik seyahat planı çıkar.
              iOS uygulamasını indir, videoyu yükle — gerisini biz yaparız.
            </p>
            <Link href="/signup" className="btn-primary px-6 py-3 rounded-xl text-sm inline-block">
              Ücretsiz Başla
            </Link>
          </div>
        </div>
      </main>
    </div>
  );
}
