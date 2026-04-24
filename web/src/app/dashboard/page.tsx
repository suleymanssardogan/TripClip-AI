"use client";

import React, { useEffect, useState } from "react";
import { motion } from "framer-motion";
import {
  MapPin, Clock, CheckCircle2, ChevronRight,
  Globe2, TrendingUp, Video, Sparkles,
  LogOut, Loader2, ArrowUpRight, Map,
} from "lucide-react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import Navbar from "@/components/Navbar";
import { getUserPlans, getStats, type Plan, type PlatformStats } from "@/lib/api";

/* ─── Yardımcı ─────────────────────────────────────────────────────────── */

const LOCATION_EMOJIS: Record<string, string> = {
  istanbul: "🕌", ankara: "🏛️", izmir: "🏖️", antalya: "🏝️",
  kapadokya: "🎈", trabzon: "⛰️", bodrum: "⛵", mardin: "🌙",
  default: "🗺️",
};

function locationEmoji(loc?: string): string {
  if (!loc) return LOCATION_EMOJIS.default;
  const key = loc.toLowerCase().replace(/[çğışöü]/g, c =>
    ({ ç: "c", ğ: "g", ı: "i", ş: "s", ö: "o", ü: "u" }[c] ?? c)
  );
  return LOCATION_EMOJIS[key] ?? LOCATION_EMOJIS.default;
}

const CARD_GRADIENTS = [
  "from-[#4DFFC3]/20 via-[#0F1521] to-[#8B5CF6]/20",
  "from-[#FF6B4A]/20 via-[#0F1521] to-[#4DFFC3]/20",
  "from-[#8B5CF6]/25 via-[#0F1521] to-[#FF6B4A]/15",
  "from-[#F5C842]/20 via-[#0F1521] to-[#4DFFC3]/15",
  "from-[#4DFFC3]/15 via-[#0F1521] to-[#F5C842]/20",
];

const cardVariants = {
  hidden: { opacity: 0, y: 28 },
  visible: (i: number) => ({
    opacity: 1, y: 0,
    transition: { delay: i * 0.08, duration: 0.5, ease: "easeOut" as const },
  }),
};

/* ─── Mini grafik ───────────────────────────────────────────────────────── */
function MiniSparkline({ value, max }: { value: number; max: number }) {
  const pct = max > 0 ? Math.min(value / max, 1) : 0;
  const pts = [0, 20, 10, 35, 25, 45, 40, 60, 50, 100 * pct]
    .map((y, x) => `${x * 11},${60 - y * 0.55}`).join(" ");
  return (
    <svg viewBox="0 0 100 60" className="w-full h-12 mt-2" preserveAspectRatio="none">
      <defs>
        <linearGradient id="sg" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" stopColor="#FF6B4A" stopOpacity="0.6" />
          <stop offset="100%" stopColor="#F5C842" stopOpacity="0.9" />
        </linearGradient>
      </defs>
      <polyline points={pts} fill="none" stroke="url(#sg)" strokeWidth="2.5"
        strokeLinecap="round" strokeLinejoin="round" />
      <circle cx={99} cy={60 - 100 * pct * 0.55} r="4" fill="#F5C842" />
    </svg>
  );
}

/* ─── Trip card (liste satırı) ─────────────────────────────────────────── */
function TripRow({ plan, index }: { plan: Plan; index: number }) {
  const router = useRouter();
  const isCompleted = plan.status === "completed" || plan.status === "COMPLETED";
  const title = plan.top_location
    ? `${plan.top_location.charAt(0).toUpperCase()}${plan.top_location.slice(1)} Gezisi`
    : plan.filename.replace(/\.[^.]+$/, "").replace(/[-_]/g, " ");

  return (
    <motion.div
      custom={index} variants={cardVariants} initial="hidden" animate="visible"
      onClick={() => isCompleted && router.push(`/analyze/${plan.id}`)}
      className={`
        group flex items-center gap-5 p-4 rounded-3xl border transition-all duration-300
        ${isCompleted
          ? "bg-white/[0.03] border-white/[0.07] hover:border-neon/20 hover:bg-white/[0.06] cursor-pointer"
          : "bg-white/[0.02] border-white/[0.04] opacity-60"
        }
      `}
    >
      {/* İkon */}
      <div className={`
        w-14 h-14 flex-shrink-0 rounded-2xl flex items-center justify-center text-2xl
        ${isCompleted ? "bg-neon/8 border border-neon/15" : "bg-white/5 border border-white/8"}
      `}>
        {locationEmoji(plan.top_location ?? undefined)}
      </div>

      {/* Bilgi */}
      <div className="flex-1 min-w-0">
        <h3 className="font-semibold text-ice text-sm truncate group-hover:text-neon transition-colors">
          {title}
        </h3>
        <div className="flex items-center gap-3 text-xs text-muted mt-1">
          <span className="flex items-center gap-1">
            <MapPin className="w-3 h-3" />
            {plan.locations_count ?? 0} mekan
          </span>
          <span className="flex items-center gap-1">
            <Clock className="w-3 h-3" />
            {plan.created_at ? new Date(plan.created_at).toLocaleDateString("tr-TR") : "—"}
          </span>
        </div>
      </div>

      {/* Sağ */}
      <div className="flex items-center gap-3 flex-shrink-0">
        {isCompleted
          ? <span className="badge-done">Tamamlandı</span>
          : <span className="badge-pending">İşleniyor</span>}
        {isCompleted && (
          <ChevronRight className="w-4 h-4 text-muted group-hover:text-neon transition-colors" />
        )}
      </div>
    </motion.div>
  );
}

/* ─── Ana sayfa ─────────────────────────────────────────────────────────── */
export default function DashboardPage() {
  const router = useRouter();
  const [plans, setPlans] = useState<Plan[]>([]);
  const [stats, setStats] = useState<PlatformStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [email, setEmail] = useState("");
  const username = email.split("@")[0];

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) { router.push("/login"); return; }
    const userId = Number(localStorage.getItem("user_id") ?? "0");
    setEmail(localStorage.getItem("email") ?? "");

    Promise.all([getUserPlans(userId), getStats()])
      .then(([up, st]) => { setPlans(up.plans); setStats(st); })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [router]);

  const completedCount  = plans.filter(p => ["completed","COMPLETED"].includes(p.status)).length;
  const totalLocations  = plans.reduce((a, p) => a + (p.locations_count || 0), 0);
  const latestPlan      = plans[0];
  const secondPlan      = plans[1];

  if (loading) {
    return (
      <div className="min-h-screen bg-bg flex items-center justify-center">
        <Loader2 className="w-8 h-8 text-neon animate-spin" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-bg pb-24">
      <Navbar />

      <div className="pt-28 px-4 md:px-8 max-w-7xl mx-auto">

        {/* ── Başlık ─────────────────────────────────────────────────── */}
        <motion.header
          initial={{ opacity: 0, y: -16 }} animate={{ opacity: 1, y: 0 }}
          className="flex items-center justify-between mb-8"
        >
          <div>
            <p className="text-xs font-mono text-neon/60 tracking-widest uppercase mb-1">Dashboard</p>
            <h1 className="font-display font-black text-3xl text-ice">
              Hoş geldin, <span className="text-neon">{username}</span>
            </h1>
          </div>
          <button
            onClick={() => { localStorage.clear(); router.push("/login"); }}
            className="flex items-center gap-2 text-sm text-muted hover:text-coral transition-colors"
          >
            <LogOut className="w-4 h-4" />
            <span className="hidden sm:block">Çıkış</span>
          </button>
        </motion.header>

        {/* ══════════════════════════════════════════════════════════════
            BENTO GRID
        ══════════════════════════════════════════════════════════════ */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">

          {/* ── A: Seyahat Görseli (son plan) ──────────── 1×1 ── */}
          <motion.div
            custom={0} variants={cardVariants} initial="hidden" animate="visible"
            className="bento-cell relative h-56 md:h-auto"
          >
            <div className={`
              w-full h-full min-h-[220px] flex flex-col justify-end p-6
              bg-gradient-to-br ${CARD_GRADIENTS[0]}
              border border-white/[0.07] rounded-[2rem]
            `}>
              {/* Büyük emoji arka plan */}
              <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 text-8xl opacity-20 select-none pointer-events-none">
                {locationEmoji(latestPlan?.top_location ?? undefined)}
              </div>
              <div className="absolute inset-0 bg-gradient-to-t from-[#080B14]/80 to-transparent rounded-[2rem]" />

              <div className="relative z-10">
                {latestPlan ? (
                  <>
                    <p className="text-xs text-neon/70 font-mono mb-1">Son Gezi</p>
                    <h3 className="font-display font-bold text-xl text-ice leading-tight">
                      {latestPlan.top_location
                        ? `${latestPlan.top_location.charAt(0).toUpperCase()}${latestPlan.top_location.slice(1)}`
                        : "Analiz Ediliyor"}
                    </h3>
                    <p className="text-muted text-xs mt-1">{latestPlan.locations_count ?? 0} lokasyon tespit edildi</p>
                  </>
                ) : (
                  <p className="text-muted text-sm">Henüz video yok</p>
                )}
              </div>
            </div>
          </motion.div>

          {/* ── B: AI Stats (turuncu) ───────────────────── 1×1 ── */}
          <motion.div
            custom={1} variants={cardVariants} initial="hidden" animate="visible"
            className="bento-cell bento-orange p-6 flex flex-col justify-between min-h-[220px]"
          >
            <div className="flex items-start justify-between">
              <div>
                <p className="text-xs text-coral/70 font-mono tracking-widest uppercase">Analiz Özeti</p>
                <p className="font-serif font-bold text-5xl text-ice mt-2 leading-none">{completedCount}</p>
                <p className="text-coral/80 text-sm mt-1">tamamlanan analiz</p>
              </div>
              <div className="w-10 h-10 rounded-xl bg-coral/10 border border-coral/20 flex items-center justify-center">
                <TrendingUp className="w-5 h-5 text-coral" />
              </div>
            </div>
            <MiniSparkline value={completedCount} max={Math.max(plans.length, 1)} />
            <div className="flex items-center justify-between mt-2">
              <p className="text-xs text-muted">Toplam video: {plans.length}</p>
              <span className="text-xs text-coral/80 font-mono">
                {plans.length > 0 ? Math.round((completedCount / plans.length) * 100) : 0}%
              </span>
            </div>
          </motion.div>

          {/* ── C: Platform Stats ──────────────────────── 1×1 ── */}
          <motion.div
            custom={2} variants={cardVariants} initial="hidden" animate="visible"
            className="bento-cell bento-green p-6 flex flex-col justify-between min-h-[220px]"
          >
            <div className="flex items-start justify-between">
              <div>
                <p className="text-xs text-neon/60 font-mono tracking-widest uppercase">Keşifler</p>
                <p className="font-serif font-bold text-5xl text-ice mt-2 leading-none">{totalLocations}</p>
                <p className="text-neon/70 text-sm mt-1">toplam mekan</p>
              </div>
              <div className="w-10 h-10 rounded-xl bg-neon/10 border border-neon/20 flex items-center justify-center">
                <Globe2 className="w-5 h-5 text-neon" />
              </div>
            </div>

            {stats && (
              <div className="grid grid-cols-2 gap-3 mt-4">
                {[
                  { label: "Platform Şehir", value: stats.total_cities },
                  { label: "Kullanıcı", value: stats.total_users },
                ].map((s, i) => (
                  <div key={i} className="bg-white/5 rounded-2xl p-3">
                    <p className="font-display font-black text-2xl text-neon">{s.value}</p>
                    <p className="text-[10px] text-muted mt-0.5">{s.label}</p>
                  </div>
                ))}
              </div>
            )}
          </motion.div>

          {/* ── D: Hero Slogan ─────────────────────── 1×2 tall ── */}
          <motion.div
            custom={3} variants={cardVariants} initial="hidden" animate="visible"
            className="bento-cell bento-navy p-8 flex flex-col justify-between md:row-span-2 min-h-[260px]"
          >
            {/* Dekoratif arka plan orb */}
            <div className="absolute w-48 h-48 rounded-full bg-violet/15 blur-3xl -top-10 -right-10 pointer-events-none" />

            <div className="relative z-10">
              <div className="inline-flex items-center gap-2 bg-violet/10 border border-violet/20 rounded-full px-3 py-1 mb-6">
                <Sparkles className="w-3 h-3 text-violet" />
                <span className="text-xs text-violet font-mono">AI Powered</span>
              </div>
              <h2 className="font-serif font-black text-ice leading-[1.05]"
                style={{ fontSize: "clamp(2.5rem, 5vw, 4rem)" }}>
                Gezi<br />
                <span className="gradient-text-neon">Planlarım</span>
              </h2>
              <p className="text-muted text-sm mt-4 leading-relaxed max-w-xs">
                Videolarından çıkarılan mekanlar, rotalar ve seyahat ipuçları — hepsi burada.
              </p>
            </div>

            <div className="relative z-10 flex flex-col gap-3 mt-6">
              <Link
                href="/explore"
                className="flex items-center justify-between w-full bg-violet/10 border border-violet/20 hover:border-violet/40 rounded-2xl px-5 py-3.5 transition-all group"
              >
                <span className="text-sm font-semibold text-ice">Gezileri Keşfet</span>
                <ArrowUpRight className="w-4 h-4 text-violet group-hover:translate-x-0.5 group-hover:-translate-y-0.5 transition-transform" />
              </Link>
              <div className="flex items-center gap-3 px-2">
                <div className="glow-dot" />
                <span className="text-xs text-neon/60 font-mono">
                  {plans.length} video analiz edildi
                </span>
              </div>
            </div>
          </motion.div>

          {/* ── E: İkinci seyahat görseli (geniş) ────── 2×1 ── */}
          <motion.div
            custom={4} variants={cardVariants} initial="hidden" animate="visible"
            className="bento-cell relative md:col-span-2 min-h-[220px]"
          >
            <div className={`
              w-full h-full min-h-[220px] flex flex-col justify-between p-6
              bg-gradient-to-br ${CARD_GRADIENTS[2]}
              border border-white/[0.07] rounded-[2rem]
            `}>
              <div className="absolute inset-0 rounded-[2rem] bg-gradient-to-br from-[#8B5CF6]/5 to-transparent" />

              {/* Büyük emoji */}
              <div className="absolute right-8 top-1/2 -translate-y-1/2 text-[7rem] opacity-15 select-none pointer-events-none">
                {locationEmoji(secondPlan?.top_location ?? undefined)}
              </div>

              <div className="relative z-10 flex items-start justify-between">
                <div>
                  <p className="text-xs text-violet/70 font-mono tracking-widest uppercase mb-1">Öne Çıkan Rota</p>
                  {secondPlan ? (
                    <h3 className="font-display font-bold text-2xl text-ice">
                      {secondPlan.top_location
                        ? `${secondPlan.top_location.charAt(0).toUpperCase()}${secondPlan.top_location.slice(1)} Güzergahı`
                        : "Rota Analizi"}
                    </h3>
                  ) : (
                    <h3 className="font-display font-bold text-2xl text-ice">Harika Rotalar Seni Bekliyor</h3>
                  )}
                </div>
                <div className="w-10 h-10 rounded-xl bg-violet/10 border border-violet/25 flex items-center justify-center">
                  <Map className="w-5 h-5 text-violet" />
                </div>
              </div>

              <div className="relative z-10 flex items-end justify-between">
                <div className="flex gap-2">
                  {plans.slice(0, 4).map((p, i) => (
                    <div key={i}
                      className="w-10 h-10 rounded-xl bg-white/8 border border-white/10 flex items-center justify-center text-lg"
                      title={p.top_location ?? ""}
                    >
                      {locationEmoji(p.top_location ?? undefined)}
                    </div>
                  ))}
                  {plans.length > 4 && (
                    <div className="w-10 h-10 rounded-xl bg-white/8 border border-white/10 flex items-center justify-center text-xs text-muted font-bold">
                      +{plans.length - 4}
                    </div>
                  )}
                </div>
                {secondPlan && (
                  <Link href={`/analyze/${secondPlan.id}`}
                    className="flex items-center gap-1.5 text-xs text-violet border border-violet/25 bg-violet/10 hover:bg-violet/20 px-3 py-1.5 rounded-xl transition-all"
                  >
                    Detay <ArrowUpRight className="w-3 h-3" />
                  </Link>
                )}
              </div>
            </div>
          </motion.div>

          {/* ── F: Kullanıcı CTA (gold) ─────────────── 1×1 ── */}
          <motion.div
            custom={5} variants={cardVariants} initial="hidden" animate="visible"
            className="bento-cell bento-gold p-6 flex flex-col justify-between min-h-[180px]"
          >
            <div className="flex items-start gap-3">
              {/* Avatar */}
              <div className="w-12 h-12 rounded-2xl bg-[#080B14]/15 flex items-center justify-center text-2xl flex-shrink-0">
                ✈️
              </div>
              <div>
                <p className="font-display font-black text-[#080B14] text-lg leading-tight">
                  Mobil uygulamadan<br />video yükle
                </p>
                <p className="text-[#080B14]/60 text-xs mt-1">iOS · Ücretsiz</p>
              </div>
            </div>
            <button className="btn-gold w-full py-3 rounded-2xl text-sm font-black mt-4">
              iOS Uygulaması →
            </button>
          </motion.div>

          {/* ── G: Son konum görseli ──────────────────── 1×1 ── */}
          <motion.div
            custom={6} variants={cardVariants} initial="hidden" animate="visible"
            className="bento-cell relative min-h-[180px]"
          >
            <div className={`
              w-full h-full min-h-[180px] flex flex-col justify-end p-5
              bg-gradient-to-br ${CARD_GRADIENTS[3]}
              border border-white/[0.07] rounded-[2rem]
            `}>
              <div className="absolute inset-0 rounded-[2rem] bg-gradient-to-t from-[#080B14]/75 to-transparent" />
              <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 text-7xl opacity-25 select-none">
                {locationEmoji(plans[2]?.top_location ?? undefined)}
              </div>
              <div className="relative z-10">
                {plans[2] ? (
                  <>
                    <p className="text-[10px] text-gold/80 font-mono uppercase tracking-widest mb-1">Keşfedildi</p>
                    <p className="font-display font-bold text-ice text-base">
                      {plans[2].top_location ?? "Rota"}
                    </p>
                    <p className="text-muted text-xs">{plans[2].locations_count ?? 0} mekan</p>
                  </>
                ) : (
                  <p className="text-muted text-xs">Daha fazla keşfet</p>
                )}
              </div>
            </div>
          </motion.div>

        </div>
        {/* ═══════════════════════════════ BENTO END ════════════════════════ */}

        {/* ── İstatistik bar (platform) ──────────────────────────────── */}
        {stats && (
          <motion.div
            custom={7} variants={cardVariants} initial="hidden" animate="visible"
            className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-8"
          >
            {[
              { label: "Toplam Analiz",   value: stats.total_videos,     icon: Video,         color: "text-neon" },
              { label: "Tamamlanan",      value: stats.completed_videos, icon: CheckCircle2,  color: "text-emerald-400" },
              { label: "Kullanıcı",       value: stats.total_users,      icon: Globe2,        color: "text-violet" },
              { label: "Şehir",           value: stats.total_cities,     icon: MapPin,        color: "text-coral" },
            ].map((s, i) => (
              <div key={i}
                className="bg-white/[0.03] border border-white/[0.06] rounded-3xl p-4 flex items-center gap-3">
                <s.icon className={`w-5 h-5 ${s.color} flex-shrink-0`} />
                <div>
                  <p className={`text-xl font-black font-display ${s.color}`}>{s.value}</p>
                  <p className="text-[10px] text-muted uppercase tracking-wider">{s.label}</p>
                </div>
              </div>
            ))}
          </motion.div>
        )}

        {/* ── Gezi listesi ──────────────────────────────────────────── */}
        <section>
          <div className="flex items-center justify-between mb-5">
            <h2 className="font-display font-bold text-xl text-ice">Gezi Geçmişim</h2>
            <span className="text-xs text-muted">{plans.length} video</span>
          </div>

          {plans.length === 0 ? (
            <div className="text-center py-20 bento-cell bento-dark border border-white/5">
              <div className="text-6xl mb-4">🗺️</div>
              <p className="text-ice font-semibold mb-2">Henüz video analiz edilmedi</p>
              <p className="text-muted text-sm">iOS uygulamasından ilk videonu yükle.</p>
            </div>
          ) : (
            <div className="space-y-3">
              {plans.map((plan, i) => (
                <TripRow key={plan.id} plan={plan} index={i} />
              ))}
            </div>
          )}
        </section>

      </div>
    </div>
  );
}
