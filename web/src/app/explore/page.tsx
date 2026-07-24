"use client";

import React, { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Search, MapPin, Clock, ArrowRight, Filter, RotateCcw, AlertTriangle } from "lucide-react";
import Navbar from "@/components/Navbar";
import Link from "next/link";
import { getPlans, getStats, Plan, PlatformStats } from "@/lib/api";

/* ─── Yardımcı ───────────────────────────────────────────── */
const UUID_RE = /^[0-9a-f-]{8,}$/i;
const TRAVEL_NAMES = [
  "Yaz Gezisi", "Keşif Turu", "Gezi Kaydı", "Seyahat Anısı",
  "Şehir Turu", "Macera Kaydı", "Tatil Anısı", "Rota Kaydı",
];

function planTitle(plan: Plan, index: number): string {
  if (plan.top_location) {
    const loc = plan.top_location;
    return `${loc.charAt(0).toUpperCase()}${loc.slice(1)} Gezisi`;
  }
  const raw = plan.filename.replace(/\.[^.]+$/, "").replace(/[-_]/g, " ").trim();
  const looksLikeUUID = UUID_RE.test(raw.replace(/\s/g, "")) || raw.length < 4;
  if (looksLikeUUID) {
    const date = plan.created_at
      ? new Date(plan.created_at).toLocaleDateString("tr-TR", { day: "numeric", month: "long" })
      : "";
    const name = TRAVEL_NAMES[index % TRAVEL_NAMES.length];
    return date ? `${name} · ${date}` : `${name} #${plan.id}`;
  }
  return raw.replace(/\b\w/g, c => c.toUpperCase());
}

/* ─── Sabitler ────────────────────────────────────────────── */
const CITY_FILTERS = [
  "Tümü", "İstanbul", "Ankara", "İzmir", "Antalya",
  "Gaziantep", "Kapadokya", "Trabzon", "Bodrum", "Mardin",
];

/* ─── Plan kartı ──────────────────────────────────────────── */
function PlanCard({ plan, index }: { plan: Plan; index: number }) {
  const city    = plan.top_location ?? "Türkiye";
  const created = new Date(plan.created_at).toLocaleDateString("tr-TR", {
    day: "numeric", month: "long", year: "numeric",
  });

  return (
    <motion.div
      initial={{ opacity: 0, y: 24 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.05, duration: 0.5, ease: "easeOut" }}
    >
      <Link href={`/analyze/${plan.id}`} className="block group">
        <div className="bg-surface border border-border rounded-lg overflow-hidden hover:border-border-strong hover:-translate-y-0.5 transition-all">

          {/* Görsel alanı */}
          <div className="relative overflow-hidden bg-surface2" style={{ height: "160px" }}>
            <div className="w-full h-full flex items-center justify-center">
              <MapPin className="w-8 h-8 text-text-tertiary" />
            </div>
            <div className="absolute top-4 left-4">
              <span className="font-mono text-[10px] font-semibold px-2.5 py-1 rounded-full bg-bg/80 border border-border text-text-secondary">
                {plan.locations_count} Mekan
              </span>
            </div>
            <div className="absolute bottom-4 left-4 flex items-center gap-1.5">
              <MapPin className="w-3 h-3 text-route" />
              <span className="text-xs tracking-widest uppercase text-text-secondary">{city}</span>
            </div>
          </div>

          {/* Metin */}
          <div className="p-5">
            <h3 className="font-display font-bold text-text text-sm leading-snug mb-3
              group-hover:text-accent-text transition-colors line-clamp-1">
              {planTitle(plan, index)}
            </h3>

            {(plan.ocr_preview ?? []).length > 0 && (
              <div className="flex flex-wrap gap-1.5 mb-3">
                {(plan.ocr_preview ?? []).slice(0, 2).map((t, i) => (
                  <span key={i} className="text-[10px] text-text-tertiary border border-border
                    px-2 py-0.5 rounded-full">
                    {t}
                  </span>
                ))}
              </div>
            )}

            <div className="flex items-center justify-between pt-3 border-t border-border">
              <span className="flex items-center gap-1.5 text-[11px] text-text-tertiary">
                <Clock className="w-3 h-3" />
                {created}
              </span>
              <span className="flex items-center gap-1 text-[11px] text-accent-text font-semibold
                group-hover:gap-2 transition-all">
                Keşfet <ArrowRight className="w-3 h-3" />
              </span>
            </div>
          </div>
        </div>
      </Link>
    </motion.div>
  );
}

/* ─── Skeleton ────────────────────────────────────────────── */
function Skeleton() {
  return (
    <div className="bg-surface border border-border rounded-lg overflow-hidden animate-pulse">
      <div className="bg-surface2" style={{ height: "160px" }} />
      <div className="p-5 space-y-3">
        <div className="h-4 bg-surface2 rounded w-3/4" />
        <div className="h-3 bg-surface2 rounded w-1/2" />
        <div className="h-px bg-border mt-4" />
      </div>
    </div>
  );
}

/* ─── Ana sayfa ─────────────────────────────────────────────── */
export default function ExplorePage() {
  const [plans, setPlans]     = useState<Plan[]>([]);
  const [stats, setStats]     = useState<PlatformStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState(false);
  const [search, setSearch]   = useState("");
  const [city, setCity]       = useState("Tümü");
  const [offset, setOffset]   = useState(0);
  const [total, setTotal]     = useState(0);
  const LIMIT = 12;

  const fetchPlans = useCallback(async (cityFilter: string, off: number) => {
    setLoading(true);
    try {
      const params: { city?: string; limit: number; offset: number } = { limit: LIMIT, offset: off };
      if (cityFilter !== "Tümü") params.city = cityFilter;
      const res = await getPlans(params);
      setPlans(res.plans);
      setTotal(res.total);
      setError(false);
    } catch {
      setError(true);
      setPlans([]);
    }
    finally { setLoading(false); }
  }, []);

  useEffect(() => {
    setTimeout(() => {
      fetchPlans(city, 0);
      getStats().then(setStats).catch(() => {});
    }, 0);
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

      {/* ── Hero ────────────────────────────────────────── */}
      <section className="relative pt-36 pb-20 px-8">
        <div className="max-w-7xl mx-auto">
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
            className="flex flex-col md:flex-row md:items-end justify-between gap-8">

            <div>
              <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}
                className="inline-flex items-center gap-2.5 mb-5 px-4 py-1.5 rounded-full
                  border border-border bg-surface2">
                <span className="glow-dot" />
                <span className="font-mono text-xs text-text-secondary tracking-widest uppercase">Keşfet</span>
              </motion.div>

              <h1 className="font-display font-black text-text leading-tight"
                style={{ fontSize: "clamp(2.25rem, 4.5vw, 4rem)" }}>
                Gerçek Seyahat<br />
                <span className="text-accent-text">Deneyimleri</span>
              </h1>
            </div>

            {stats && (
              <div className="flex gap-10 md:gap-16 flex-shrink-0 pb-2">
                {[
                  { val: stats.completed_videos, label: "Video Analizi" },
                  { val: stats.total_cities,     label: "Şehir" },
                ].map((s, i) => (
                  <div key={i} className="text-right">
                    <p className="font-mono font-semibold text-text text-3xl tabular-nums">{s.val}+</p>
                    <p className="font-mono text-xs text-text-tertiary uppercase tracking-widest mt-1">{s.label}</p>
                  </div>
                ))}
              </div>
            )}
          </motion.div>

          <p className="text-text-secondary mt-6 max-w-xl leading-relaxed">
            AI&apos;ın analiz ettiği gerçek gezi videolarından çıkarılan mekanlar, rotalar ve seyahat hikâyeleri.
          </p>
        </div>
      </section>

      {/* ── Arama + filtreler ───────────────────────────────── */}
      <div className="sticky top-[68px] z-40 bg-bg/90 backdrop-blur-lg border-b border-border">
        <div className="max-w-7xl mx-auto px-8 py-3 flex items-center gap-4">

          {/* Arama */}
          <div className="relative flex-1 max-w-sm">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-text-tertiary" />
            <input
              type="text" value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Şehir veya mekan ara..."
              className="w-full bg-surface2 border border-border-strong rounded-md pl-9 pr-4 py-2.5
                text-text placeholder:text-text-tertiary text-sm
                focus:outline-none focus:border-accent-text transition-colors"
            />
          </div>

          {/* Şehir filtreleri */}
          <div className="hidden md:flex items-center gap-1 overflow-x-auto no-scrollbar">
            <Filter className="w-3.5 h-3.5 text-text-tertiary flex-shrink-0 mr-2" />
            {CITY_FILTERS.map(c => (
              <button key={c}
                onClick={() => { setCity(c); setOffset(0); }}
                className={`flex-shrink-0 px-3 py-1.5 text-xs rounded-md tracking-wide transition-all ${
                  city === c
                    ? "bg-accent text-on-accent font-bold"
                    : "text-text-secondary hover:text-text hover:bg-surface2"
                }`}>
                {c}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* ── Plan grid ────────────────────────────────────────── */}
      <main className="relative max-w-7xl mx-auto px-8 py-16">

        {/* Sonuç sayısı */}
        {!loading && filtered.length > 0 && (
          <div className="flex items-center justify-between mb-8">
            <p className="text-text-tertiary text-sm">
              <span className="text-text font-semibold">{total}</span> gezi analizi
              {city !== "Tümü" && <span className="text-accent-text"> · {city}</span>}
            </p>
          </div>
        )}

        {loading ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6">
            {Array.from({ length: 8 }).map((_, i) => <Skeleton key={i} />)}
          </div>
        ) : error ? (
          <div className="text-center py-32">
            <AlertTriangle className="w-10 h-10 text-destructive mx-auto mb-4" />
            <h3 className="font-display font-bold text-text text-xl mb-2">Geziler yüklenemedi</h3>
            <p className="text-text-secondary text-sm mb-8">Sunucuya ulaşılamadı. İnternet bağlantınızı kontrol edip tekrar deneyin.</p>
            <button
              onClick={() => fetchPlans(city, offset)}
              className="flex items-center gap-2 mx-auto text-xs px-5 py-2.5 rounded-md bg-route/10 border border-route/25 text-route hover:bg-route/20 transition-colors">
              <RotateCcw className="w-3 h-3" /> Tekrar Dene
            </button>
          </div>
        ) : filtered.length === 0 ? (
          <div className="text-center py-32">
            <MapPin className="w-10 h-10 text-text-tertiary mx-auto mb-4" />
            <h3 className="font-display font-bold text-text text-xl mb-2">
              {total === 0 ? "Henüz video analiz edilmedi" : "Sonuç bulunamadı"}
            </h3>
            <p className="text-text-secondary text-sm mb-8">
              {total === 0 ? "iOS uygulamasından ilk videoyu yükle!" : "Farklı bir arama dene"}
            </p>
            {search && (
              <button onClick={() => setSearch("")}
                className="flex items-center gap-2 mx-auto text-xs px-5 py-2.5 rounded-md bg-route/10 border border-route/25 text-route hover:bg-route/20 transition-colors">
                <RotateCcw className="w-3 h-3" /> Aramayı Temizle
              </button>
            )}
          </div>
        ) : (
          <>
            <AnimatePresence mode="wait">
              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6">
                {filtered.map((plan, i) => (
                  <PlanCard key={plan.id} plan={plan} index={i} />
                ))}
              </div>
            </AnimatePresence>

            {/* Sayfalama */}
            {total > LIMIT && (
              <div className="flex items-center justify-center gap-4 mt-16 pt-8 border-t border-border">
                <button
                  onClick={() => { const o = Math.max(0, offset - LIMIT); setOffset(o); fetchPlans(city, o); }}
                  disabled={offset === 0}
                  className="text-xs py-2.5 px-6 rounded-md bg-route/10 border border-route/25 text-route hover:bg-route/20 transition-colors disabled:opacity-30">
                  ← Önceki
                </button>
                <span className="text-text-tertiary text-sm">
                  {Math.floor(offset / LIMIT) + 1} / {Math.ceil(total / LIMIT)}
                </span>
                <button
                  onClick={() => { const o = offset + LIMIT; setOffset(o); fetchPlans(city, o); }}
                  disabled={offset + LIMIT >= total}
                  className="text-xs py-2.5 px-6 rounded-md bg-accent text-on-accent hover:bg-accent-hover transition-colors disabled:opacity-30">
                  Sonraki →
                </button>
              </div>
            )}
          </>
        )}

        {/* Alt CTA */}
        <div className="mt-28 pt-16 border-t border-border text-center">
          <div className="inline-flex items-center gap-2 mb-4 px-4 py-1.5 rounded-full
            border border-border bg-surface2">
            <span className="font-mono text-xs text-text-secondary tracking-widest uppercase">Kendi Planını Oluştur</span>
          </div>
          <h2 className="font-display font-black text-text mt-2 mb-4"
            style={{ fontSize: "clamp(1.75rem, 2.8vw, 2.5rem)" }}>
            Videonu Yükle, Rotanı Keşfet
          </h2>
          <p className="text-text-secondary mb-8 max-w-md mx-auto text-sm leading-relaxed">
            iOS uygulamasından gezi videonu yükle. AI otomatik olarak mekanları tespit eder,
            haritaya işler ve sana özel rota oluşturur.
          </p>
          <Link href="/signup"
            className="inline-flex items-center gap-2 px-8 py-3.5 rounded-md text-sm font-bold bg-accent text-on-accent hover:bg-accent-hover transition-colors">
            Ücretsiz Başla <ArrowRight className="w-4 h-4" />
          </Link>
        </div>
      </main>
    </div>
  );
}
