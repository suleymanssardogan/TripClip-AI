"use client";

import React, { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Search, MapPin, Clock, ArrowRight, Filter, RotateCcw } from "lucide-react";
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

const DEST_COLORS = [
  { from: "#4DFFC3", to: "#8B5CF6" },
  { from: "#FF6B4A", to: "#4DFFC3" },
  { from: "#8B5CF6", to: "#FF6B4A" },
  { from: "#F5C842", to: "#4DFFC3" },
  { from: "#4DFFC3", to: "#F5C842" },
];

/* ─── Plan kartı ──────────────────────────────────────────── */
function PlanCard({ plan, index }: { plan: Plan; index: number }) {
  const city     = plan.top_location ?? "Türkiye";
  const colorSet = DEST_COLORS[plan.id % DEST_COLORS.length];
  const created  = new Date(plan.created_at).toLocaleDateString("tr-TR", {
    day: "numeric", month: "long", year: "numeric",
  });

  return (
    <motion.div
      initial={{ opacity: 0, y: 24 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.05, duration: 0.5, ease: "easeOut" }}
    >
      <Link href={`/analyze/${plan.id}`} className="block group">
        <div className="neon-card rounded-2xl overflow-hidden">

          {/* Görsel alanı */}
          <div className="relative overflow-hidden" style={{ height: "200px" }}>
            <div className="w-full h-full transition-transform duration-700 group-hover:scale-[1.04]"
              style={{
                background: `linear-gradient(135deg, ${colorSet.from}22 0%, ${colorSet.to}33 100%)`,
                backgroundColor: "#0A0D1A",
              }}>
              <div className="absolute inset-0"
                style={{ background: "linear-gradient(to top, rgba(8,11,20,0.8) 0%, transparent 60%)" }} />

              {/* Badge */}
              <div className="absolute top-4 left-4">
                <span className="tag">{plan.locations_count} Mekan</span>
              </div>

              {/* Şehir */}
              <div className="absolute bottom-4 left-4">
                <div className="flex items-center gap-1.5 text-ice/70 mb-1">
                  <MapPin className="w-3 h-3 text-neon" />
                  <span className="text-xs tracking-widest uppercase text-ice/80">{city}</span>
                </div>
              </div>

              {/* Gradient accent çizgi */}
              <div className="absolute bottom-0 left-0 right-0 h-[2px]"
                style={{ background: `linear-gradient(90deg, ${colorSet.from}, ${colorSet.to})` }} />
            </div>
          </div>

          {/* Metin */}
          <div className="p-5">
            <h3 className="font-display font-bold text-ice text-sm leading-snug mb-3
              group-hover:text-neon transition-colors line-clamp-1">
              {planTitle(plan, index)}
            </h3>

            {(plan.ocr_preview ?? []).length > 0 && (
              <div className="flex flex-wrap gap-1.5 mb-3">
                {(plan.ocr_preview ?? []).slice(0, 2).map((t, i) => (
                  <span key={i} className="text-[10px] text-muted border border-white/10
                    px-2 py-0.5 rounded-full">
                    {t}
                  </span>
                ))}
              </div>
            )}

            <div className="flex items-center justify-between pt-3 border-t border-white/[0.06]">
              <span className="flex items-center gap-1.5 text-[11px] text-muted">
                <Clock className="w-3 h-3" />
                {created}
              </span>
              <span className="flex items-center gap-1 text-[11px] text-neon font-semibold
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
    <div className="neon-card rounded-2xl overflow-hidden animate-pulse">
      <div className="bg-white/[0.03]" style={{ height: "200px" }} />
      <div className="p-5 space-y-3">
        <div className="h-4 bg-white/[0.05] rounded w-3/4" />
        <div className="h-3 bg-white/[0.04] rounded w-1/2" />
        <div className="h-px bg-white/[0.06] mt-4" />
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
    <div className="min-h-screen bg-bg">
      <Navbar />

      {/* Arka plan orb'lar */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden">
        <div className="orb w-[500px] h-[500px] bg-neon top-0 -left-40" />
        <div className="orb w-[400px] h-[400px] bg-violet top-1/3 -right-32" />
      </div>

      {/* ── Hero ────────────────────────────────────────── */}
      <section className="relative pt-36 pb-20 px-8">
        <div className="max-w-7xl mx-auto">
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
            className="flex flex-col md:flex-row md:items-end justify-between gap-8">

            <div>
              <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}
                className="inline-flex items-center gap-2.5 mb-5 px-4 py-1.5 rounded-full
                  border border-neon/20 bg-neon/[0.05]">
                <div className="glow-dot" />
                <span className="text-xs font-mono text-neon/80 tracking-widest uppercase">Keşfet</span>
              </motion.div>

              <h1 className="font-display font-black text-ice leading-tight"
                style={{ fontSize: "clamp(2.5rem, 5vw, 5rem)" }}>
                Gerçek Seyahat<br />
                <span className="gradient-text">Deneyimleri</span>
              </h1>
            </div>

            {stats && (
              <div className="flex gap-10 md:gap-16 flex-shrink-0 pb-2">
                {[
                  { val: stats.completed_videos, label: "Video Analizi" },
                  { val: stats.total_cities,     label: "Şehir" },
                ].map((s, i) => (
                  <div key={i} className="text-right">
                    <p className="font-display font-black text-ice text-3xl">{s.val}+</p>
                    <p className="text-xs font-mono text-neon/60 uppercase tracking-widest mt-1">{s.label}</p>
                  </div>
                ))}
              </div>
            )}
          </motion.div>

          <p className="text-muted mt-6 max-w-xl leading-relaxed">
            AI'ın analiz ettiği gerçek gezi videolarından çıkarılan mekanlar, rotalar ve seyahat hikâyeleri.
          </p>
        </div>
      </section>

      {/* ── Arama + filtreler ───────────────────────────────── */}
      <div className="sticky top-[68px] z-40 glass border-b border-white/[0.06]">
        <div className="max-w-7xl mx-auto px-8 py-3 flex items-center gap-4">

          {/* Arama */}
          <div className="relative flex-1 max-w-sm">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted" />
            <input
              type="text" value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Şehir veya mekan ara..."
              className="w-full bg-white/[0.04] border border-white/10 rounded-lg pl-9 pr-4 py-2.5
                text-ice placeholder:text-muted text-sm
                focus:outline-none focus:border-neon/40 transition-colors"
            />
          </div>

          {/* Şehir filtreleri */}
          <div className="hidden md:flex items-center gap-1 overflow-x-auto no-scrollbar">
            <Filter className="w-3.5 h-3.5 text-muted flex-shrink-0 mr-2" />
            {CITY_FILTERS.map(c => (
              <button key={c}
                onClick={() => { setCity(c); setOffset(0); }}
                className={`flex-shrink-0 px-3 py-1.5 text-xs rounded-lg tracking-wide transition-all ${
                  city === c
                    ? "bg-neon text-bg font-bold"
                    : "text-muted hover:text-ice hover:bg-white/[0.05]"
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
            <p className="text-muted text-sm">
              <span className="text-ice font-semibold">{total}</span> gezi analizi
              {city !== "Tümü" && <span className="text-neon"> · {city}</span>}
            </p>
          </div>
        )}

        {loading ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6">
            {Array.from({ length: 8 }).map((_, i) => <Skeleton key={i} />)}
          </div>
        ) : filtered.length === 0 ? (
          <div className="text-center py-32">
            <p className="text-5xl mb-4">{total === 0 ? "🗺️" : "🔍"}</p>
            <h3 className="font-display font-bold text-ice text-xl mb-2">
              {total === 0 ? "Henüz video analiz edilmedi" : "Sonuç bulunamadı"}
            </h3>
            <p className="text-muted text-sm mb-8">
              {total === 0 ? "iOS uygulamasından ilk videoyu yükle!" : "Farklı bir arama dene"}
            </p>
            {search && (
              <button onClick={() => setSearch("")}
                className="btn-neon flex items-center gap-2 mx-auto text-xs px-5 py-2.5 rounded-xl">
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
              <div className="flex items-center justify-center gap-4 mt-16 pt-8 border-t border-white/[0.06]">
                <button
                  onClick={() => { const o = Math.max(0, offset - LIMIT); setOffset(o); fetchPlans(city, o); }}
                  disabled={offset === 0}
                  className="btn-neon text-xs py-2.5 px-6 rounded-xl disabled:opacity-30">
                  ← Önceki
                </button>
                <span className="text-muted text-sm">
                  {Math.floor(offset / LIMIT) + 1} / {Math.ceil(total / LIMIT)}
                </span>
                <button
                  onClick={() => { const o = offset + LIMIT; setOffset(o); fetchPlans(city, o); }}
                  disabled={offset + LIMIT >= total}
                  className="btn-primary text-xs py-2.5 px-6 rounded-xl disabled:opacity-30">
                  Sonraki →
                </button>
              </div>
            )}
          </>
        )}

        {/* Alt CTA */}
        <div className="mt-28 pt-16 border-t border-white/[0.06] text-center">
          <div className="inline-flex items-center gap-2 mb-4 px-4 py-1.5 rounded-full
            border border-neon/20 bg-neon/[0.05]">
            <span className="text-xs font-mono text-neon/80 tracking-widest uppercase">Kendi Planını Oluştur</span>
          </div>
          <h2 className="font-display font-black text-ice mt-2 mb-4"
            style={{ fontSize: "clamp(1.8rem, 3vw, 2.8rem)" }}>
            Videonu Yükle, Rotanı Keşfet
          </h2>
          <p className="text-muted mb-8 max-w-md mx-auto text-sm leading-relaxed">
            iOS uygulamasından gezi videonu yükle. AI otomatik olarak mekanları tespit eder,
            haritaya işler ve sana özel rota oluşturur.
          </p>
          <Link href="/signup"
            className="btn-primary inline-flex items-center gap-2 px-8 py-3.5 rounded-xl text-sm">
            Ücretsiz Başla <ArrowRight className="w-4 h-4" />
          </Link>
        </div>
      </main>
    </div>
  );
}
