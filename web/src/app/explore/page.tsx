"use client";

import React, { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Search, Clock, ArrowRight, RotateCcw } from "lucide-react";
import Navbar from "@/components/Navbar";
import Link from "next/link";
import { getPlans, getStats, Plan, PlatformStats } from "@/lib/api";
import { Card } from "@/components/ui/Card";
import { Button, buttonVariants } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";

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
      transition={{ delay: index * 0.04, duration: 0.35, ease: "easeOut" }}
    >
      <Link href={`/analyze/${plan.id}`} className="block group">
        <Card hover className="h-full">

          <div className="flex h-full flex-col p-6">
            <div className="mb-5 flex items-center justify-between border-b border-border pb-4">
              <span className="text-xs font-semibold uppercase tracking-wider text-accent-text">{city}</span>
              <span className="text-xs text-text-tertiary">{plan.locations_count} mekân</span>
            </div>
            <h3 className="font-display text-xl font-bold text-text leading-snug mb-4 tracking-tight
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

            <div className="mt-auto flex items-center justify-between border-t border-border pt-4">
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
        </Card>
      </Link>
    </motion.div>
  );
}

/* ─── Skeleton ────────────────────────────────────────────── */
function Skeleton() {
  return (
    <div className="bg-surface border border-border rounded-lg overflow-hidden animate-pulse">
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
      getStats().then(setStats).catch(err => console.error("getStats failed:", err));
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
      <section className="bg-surface px-5 pb-12 pt-32 sm:px-8 lg:pt-36">
        <div className="max-w-7xl mx-auto relative">
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
            className="flex flex-col md:flex-row md:items-end justify-between gap-8">

            <div>
              <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}
                className="mb-4 text-xs font-semibold uppercase tracking-widest text-accent-text">
                Keşfet
              </motion.div>

              <h1 className="font-display font-bold tracking-[-0.055em] text-text leading-tight"
                style={{ fontSize: "clamp(2.5rem, 4.5vw, 4.25rem)" }}>
                Yeni yerler<br />
                <span className="text-accent-text">keşfet.</span>
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
            Gezi videolarından çıkan duraklara göz at. Bir sonraki yolculuğun için ilham bul.
          </p>
        </div>
      </section>

      {/* ── Arama + filtreler ───────────────────────────────── */}
      <div className="sticky top-[72px] z-40 border-y border-border bg-surface/95 backdrop-blur-lg">
        <div className="max-w-7xl mx-auto flex flex-col gap-3 px-5 py-3 sm:px-8 md:flex-row md:items-center md:gap-5">

          {/* Arama */}
          <div className="relative w-full flex-1 md:max-w-sm">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-text-tertiary" />
            <Input
              type="text" value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Şehir veya mekan ara..."
              className="pl-9 py-2.5"
            />
          </div>

          {/* Şehir filtreleri */}
          <div className="flex w-full items-center gap-1 overflow-x-auto no-scrollbar md:w-auto">
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
      <main className="relative max-w-7xl mx-auto px-5 py-14 sm:px-8">

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
          <div className="mx-auto max-w-2xl rounded-xl border border-border bg-surface px-6 py-14 text-center sm:px-10">
            <p className="text-xs font-semibold uppercase tracking-[0.17em] text-text-tertiary">Bağlantı sorunu</p>
            <h3 className="mt-3 font-display text-2xl font-bold tracking-tight text-text">Geziler şu anda yüklenemiyor.</h3>
            <p className="mx-auto mb-7 mt-3 max-w-md text-sm leading-6 text-text-secondary">İnternet bağlantını kontrol edip yeniden deneyebilirsin.</p>
            <Button variant="outline" size="sm" onClick={() => fetchPlans(city, offset)}>
              <RotateCcw className="w-3 h-3" /> Tekrar Dene
            </Button>
          </div>
        ) : filtered.length === 0 ? (
          <div className="mx-auto max-w-2xl rounded-xl border border-border bg-surface px-6 py-14 text-center sm:px-10">
            <h3 className="font-display font-bold text-text text-xl mb-2">
              {total === 0 ? "Henüz video analiz edilmedi" : "Sonuç bulunamadı"}
            </h3>
            <p className="text-text-secondary text-sm mb-8">
              {total === 0 ? "iOS uygulamasından ilk videoyu yükle!" : "Farklı bir arama dene"}
            </p>
            {search && (
              <Button variant="subtle" size="sm" onClick={() => setSearch("")}>
                <RotateCcw className="w-3 h-3" /> Aramayı Temizle
              </Button>
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
                <Button
                  variant="subtle" size="sm"
                  onClick={() => { const o = Math.max(0, offset - LIMIT); setOffset(o); fetchPlans(city, o); }}
                  disabled={offset === 0}>
                  ← Önceki
                </Button>
                <span className="text-text-tertiary text-sm">
                  {Math.floor(offset / LIMIT) + 1} / {Math.ceil(total / LIMIT)}
                </span>
                <Button
                  size="sm"
                  onClick={() => { const o = offset + LIMIT; setOffset(o); fetchPlans(city, o); }}
                  disabled={offset + LIMIT >= total}>
                  Sonraki →
                </Button>
              </div>
            )}
          </>
        )}

        {/* Alt CTA */}
        <div className="mt-24 rounded-2xl bg-surface px-6 py-12 text-center sm:px-12">
          <p className="text-xs font-bold uppercase tracking-[0.18em] text-accent-text">Kendi planını oluştur</p>
          <h2 className="font-display font-bold text-text mt-3 mb-4"
            style={{ fontSize: "clamp(1.75rem, 2.8vw, 2.5rem)" }}>
            Gördüğün yeri rotana ekle.
          </h2>
          <p className="text-text-secondary mb-8 max-w-md mx-auto text-sm leading-7">
            Gezi videonu TripClip iOS uygulamasında paylaş. Duraklarını bulup kendi planına dönüştür.
          </p>
          <Link href="/signup" className={buttonVariants({ size: "lg" }) + " text-sm"}>
            Ücretsiz Başla <ArrowRight className="w-4 h-4" />
          </Link>
        </div>
      </main>
    </div>
  );
}
