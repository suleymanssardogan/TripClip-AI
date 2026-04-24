"use client";

import React, { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Search, MapPin, Clock, ArrowRight, Filter, RotateCcw } from "lucide-react";
import LuxuryNavbar from "@/components/LuxuryNavbar";
import Link from "next/link";
import { getPlans, getStats, Plan, PlatformStats } from "@/lib/api";

/* ─── Sabitler ────────────────────────────────────────────── */
const CITY_FILTERS = [
  "Tümü", "İstanbul", "Ankara", "İzmir", "Antalya",
  "Gaziantep", "Kapadokya", "Trabzon", "Bodrum", "Mardin",
];

const DEST_COLORS = [
  { bg: "#2C1810", accent: "#8B4513" },
  { bg: "#1A1A2E", accent: "#6B4E9B" },
  { bg: "#0A2A1A", accent: "#1B7A4A" },
  { bg: "#2A1A08", accent: "#C8861A" },
  { bg: "#0A1A2A", accent: "#1A6BAA" },
];

/* ─── Plan kartı ──────────────────────────────────────────── */
function PlanCard({ plan, index }: { plan: Plan; index: number }) {
  const city    = plan.top_location ?? "Türkiye";
  const colorSet = DEST_COLORS[plan.id % DEST_COLORS.length];
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
        <div className="luxury-card overflow-hidden">

          {/* Görsel alanı */}
          <div className="relative overflow-hidden" style={{ height: "220px" }}>
            <div className="w-full h-full transition-transform duration-700 group-hover:scale-[1.04]"
              style={{
                background: `linear-gradient(135deg, ${colorSet.bg} 0%, ${colorSet.accent}99 100%)`,
                height: "220px",
              }}>
              {/* Overlay */}
              <div className="absolute inset-0"
                style={{ background: "linear-gradient(to top, rgba(0,0,0,0.55) 0%, transparent 50%)" }} />

              {/* Mekan sayısı badge */}
              <div className="absolute top-4 left-4">
                <span className="text-[10px] font-semibold tracking-[0.15em] uppercase
                  bg-white/10 backdrop-blur-sm text-white px-3 py-1 border border-white/20">
                  {plan.locations_count} Mekan
                </span>
              </div>

              {/* Şehir adı */}
              <div className="absolute bottom-4 left-5">
                <div className="flex items-center gap-1.5 text-white/80 mb-1">
                  <MapPin className="w-3 h-3" />
                  <span className="text-xs tracking-widest uppercase">{city}</span>
                </div>
              </div>
            </div>
          </div>

          {/* Metin */}
          <div className="p-5">
            <h3 className="font-serif font-bold text-charcoal text-[15px] leading-snug mb-2
              group-hover:text-gold transition-colors">
              {plan.filename.replace(/\.[^.]+$/, "").replace(/[-_]/g, " ")}
            </h3>

            {plan.ocr_preview.length > 0 && (
              <div className="flex flex-wrap gap-1.5 mb-3">
                {plan.ocr_preview.slice(0, 2).map((t, i) => (
                  <span key={i} className="text-[10px] text-charcoal-lt tracking-wide
                    border border-warm-border px-2 py-0.5">
                    {t}
                  </span>
                ))}
              </div>
            )}

            <div className="flex items-center justify-between pt-3 border-t border-warm-border">
              <span className="flex items-center gap-1.5 text-[11px] text-charcoal-lt tracking-wide">
                <Clock className="w-3 h-3" />
                {created}
              </span>
              <span className="luxury-link text-[10px]">
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
    <div className="luxury-card overflow-hidden animate-pulse">
      <div className="bg-cream-warm" style={{ height: "220px" }} />
      <div className="p-5 space-y-3">
        <div className="h-4 bg-cream-warm rounded w-3/4" />
        <div className="h-3 bg-cream-warm rounded w-1/2" />
        <div className="h-px bg-warm-border mt-4" />
      </div>
    </div>
  );
}

/* ─── Ana sayfa ─────────────────────────────────────────────── */
export default function ExplorePage() {
  const [plans, setPlans]     = useState<Plan[]>([]);
  const [stats, setStats]     = useState<PlatformStats | null>(null);
  const [loading, setLoading] = useState(true);
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
    } catch { setPlans([]); }
    finally { setLoading(false); }
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
    <div className="light-page min-h-screen">
      <LuxuryNavbar />

      {/* ── Hero editorial başlık ────────────────────────────── */}
      <section className="luxury-section-warm pt-36 pb-20 px-8">
        <div className="max-w-7xl mx-auto">
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
            className="flex flex-col md:flex-row md:items-end justify-between gap-8">

            <div>
              <span className="luxury-label">Keşfet</span>
              <h1 className="font-serif font-black text-charcoal mt-3 leading-tight"
                style={{ fontSize: "clamp(2.5rem, 5vw, 5rem)" }}>
                Gerçek Seyahat<br />
                <span style={{ color: "#C8A96E" }}>Deneyimleri</span>
              </h1>
            </div>

            {stats && (
              <div className="flex gap-10 md:gap-16 flex-shrink-0 pb-2">
                {[
                  { val: stats.completed_videos, label: "Video Analizi" },
                  { val: stats.total_cities,     label: "Şehir" },
                ].map((s, i) => (
                  <div key={i} className="text-right">
                    <p className="font-serif font-black text-charcoal text-3xl">{s.val}+</p>
                    <p className="luxury-label mt-1">{s.label}</p>
                  </div>
                ))}
              </div>
            )}
          </motion.div>

          <p className="text-charcoal-mid mt-6 max-w-xl leading-relaxed">
            AI'ın analiz ettiği gerçek gezi videolarından çıkarılan mekanlar, rotalar ve seyahat hikâyeleri.
          </p>
        </div>
      </section>

      {/* ── Arama + filtreler ───────────────────────────────── */}
      <div className="sticky top-[68px] z-40 bg-cream border-b border-warm-border">
        <div className="max-w-7xl mx-auto px-8 py-3 flex items-center gap-4">

          {/* Arama */}
          <div className="relative flex-1 max-w-sm">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-charcoal-lt" />
            <input
              type="text" value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Şehir veya mekan ara..."
              className="w-full bg-transparent border border-warm-border pl-9 pr-4 py-2.5
                text-charcoal placeholder:text-charcoal-lt text-sm tracking-wide
                focus:outline-none focus:border-charcoal transition-colors"
            />
          </div>

          {/* Şehir filtreleri */}
          <div className="hidden md:flex items-center gap-1 overflow-x-auto no-scrollbar">
            <Filter className="w-3.5 h-3.5 text-charcoal-lt flex-shrink-0 mr-2" />
            {CITY_FILTERS.map(c => (
              <button key={c}
                onClick={() => { setCity(c); setOffset(0); }}
                className={`flex-shrink-0 px-3 py-1.5 text-xs tracking-wide transition-all ${
                  city === c
                    ? "bg-charcoal text-cream font-semibold"
                    : "text-charcoal-mid hover:text-charcoal hover:bg-cream-warm"
                }`}>
                {c}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* ── Plan grid ────────────────────────────────────────── */}
      <main className="max-w-7xl mx-auto px-8 py-16">

        {/* Sonuç sayısı */}
        {!loading && filtered.length > 0 && (
          <div className="flex items-center justify-between mb-8">
            <p className="text-charcoal-lt text-sm tracking-wide">
              <span className="text-charcoal font-semibold">{total}</span> gezi analizi
              {city !== "Tümü" && <span> · {city}</span>}
            </p>
          </div>
        )}

        {loading ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6">
            {Array.from({ length: 8 }).map((_, i) => <Skeleton key={i} />)}
          </div>
        ) : filtered.length === 0 ? (
          <div className="text-center py-32">
            <p className="font-serif text-4xl text-charcoal mb-3">
              {total === 0 ? "🗺️" : "🔍"}
            </p>
            <h3 className="font-serif font-bold text-charcoal text-xl mb-2">
              {total === 0 ? "Henüz video analiz edilmedi" : "Sonuç bulunamadı"}
            </h3>
            <p className="text-charcoal-lt text-sm mb-8">
              {total === 0 ? "iOS uygulamasından ilk videoyu yükle!" : "Farklı bir arama dene"}
            </p>
            {search && (
              <button onClick={() => setSearch("")}
                className="luxury-btn-outline flex items-center gap-2 mx-auto text-xs">
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
              <div className="flex items-center justify-center gap-4 mt-16 pt-8 border-t border-warm-border">
                <button
                  onClick={() => { const o = Math.max(0, offset - LIMIT); setOffset(o); fetchPlans(city, o); }}
                  disabled={offset === 0}
                  className="luxury-btn-outline text-xs py-2 px-6 disabled:opacity-30">
                  ← Önceki
                </button>
                <span className="text-charcoal-lt text-sm tracking-wider">
                  {Math.floor(offset / LIMIT) + 1} / {Math.ceil(total / LIMIT)}
                </span>
                <button
                  onClick={() => { const o = offset + LIMIT; setOffset(o); fetchPlans(city, o); }}
                  disabled={offset + LIMIT >= total}
                  className="luxury-btn text-xs py-2 px-6 disabled:opacity-30">
                  Sonraki →
                </button>
              </div>
            )}
          </>
        )}

        {/* Alt CTA */}
        <div className="mt-28 pt-16 border-t border-warm-border text-center">
          <span className="luxury-label">Kendi Planını Oluştur</span>
          <h2 className="font-serif font-black text-charcoal mt-3 mb-4"
            style={{ fontSize: "clamp(1.8rem, 3vw, 2.8rem)" }}>
            Videonu Yükle, Rotanı Keşfet
          </h2>
          <p className="text-charcoal-mid mb-8 max-w-md mx-auto text-sm leading-relaxed">
            iOS uygulamasından gezi videonu yükle. AI otomatik olarak mekanları tespit eder,
            haritaya işler ve sana özel rota oluşturur.
          </p>
          <Link href="/signup" className="luxury-btn">
            Ücretsiz Başla <ArrowRight className="w-4 h-4" />
          </Link>
        </div>
      </main>
    </div>
  );
}
