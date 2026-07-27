"use client";

import React, { useEffect, useState } from "react";
import { motion } from "framer-motion";
import {
  MapPin, Clock, CheckCircle2, ChevronRight,
  Globe2, Video, LogOut, Loader2, Plus, AlertTriangle, RotateCcw,
} from "lucide-react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import Navbar from "@/components/Navbar";
import { getUserPlans, getStats, logout, type Plan, type PlatformStats } from "@/lib/api";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button, buttonVariants } from "@/components/ui/Button";

/* ─── Yardımcı ─────────────────────────────────────────────────────────── */

const UUID_RE = /^[0-9a-f-]{8,}$/i;
const TRAVEL_NAMES = [
  "Yaz Gezisi", "Keşif Turu", "Gezi Kaydı", "Seyahat Anısı",
  "Şehir Turu", "Macera Kaydı", "Tatil Anısı", "Rota Kaydı",
];

function planTitle(plan: Plan, index: number): string {
  // top_location varsa "İstanbul Gezisi"
  if (plan.top_location) {
    const loc = plan.top_location;
    return `${loc.charAt(0).toUpperCase()}${loc.slice(1)} Gezisi`;
  }

  // Dosya adı UUID ya da çok kısa/anlamsızsa tarih + sıra ile isimlendir
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

const cardVariants = {
  hidden: { opacity: 0, y: 20 },
  visible: (i: number) => ({
    opacity: 1, y: 0,
    transition: { delay: Math.min(i, 8) * 0.04, duration: 0.4, ease: "easeOut" as const },
  }),
};

/* ─── Trip card (grid hücresi) ──────────────────────────────────────────── */
function TripCard({ plan, index }: { plan: Plan; index: number }) {
  const router = useRouter();
  const isCompleted = plan.status === "completed" || plan.status === "COMPLETED";
  const title = planTitle(plan, index);

  return (
    <motion.div custom={index} variants={cardVariants} initial="hidden" animate="visible">
      <Card
        hover={isCompleted}
        onClick={() => isCompleted && router.push(`/analyze/${plan.id}`)}
        className={`group ${isCompleted ? "cursor-pointer" : "opacity-70"}`}
      >
        <div className="h-20 flex items-center justify-center text-3xl bg-surface2">
          {locationEmoji(plan.top_location ?? undefined)}
        </div>
        <div className="p-4">
          <div className="flex items-start justify-between gap-2 mb-2">
            <h3 className="font-display font-bold text-text text-sm leading-snug">{title}</h3>
            {isCompleted
              ? <Badge variant="success" className="shrink-0">Tamamlandı</Badge>
              : <Badge variant="warning" className="shrink-0">İşleniyor</Badge>}
          </div>
          <div className="flex items-center gap-3 text-xs text-text-tertiary">
            <span className="flex items-center gap-1">
              <MapPin className="w-3 h-3" />
              {plan.locations_count ?? 0} mekan
            </span>
            <span className="flex items-center gap-1">
              <Clock className="w-3 h-3" />
              {plan.created_at ? new Date(plan.created_at).toLocaleDateString("tr-TR") : "—"}
            </span>
          </div>
          {isCompleted && (
            <div className="flex items-center gap-1 mt-3 text-xs text-text-secondary group-hover:text-text">
              Detayları gör <ChevronRight className="w-3 h-3" />
            </div>
          )}
        </div>
      </Card>
    </motion.div>
  );
}

/* ─── Ana sayfa ─────────────────────────────────────────────────────────── */
export default function DashboardPage() {
  const router = useRouter();
  const [plans, setPlans] = useState<Plan[]>([]);
  const [stats, setStats] = useState<PlatformStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [email, setEmail] = useState("");
  const username = email.split("@")[0];

  function load() {
    const userId = Number(localStorage.getItem("user_id") ?? "0");
    const storedEmail = localStorage.getItem("email") ?? "";

    Promise.all([getUserPlans(userId), getStats()])
      .then(([up, st]) => {
        setTimeout(() => {
          setEmail(storedEmail);
          setPlans(up.plans);
          setStats(st);
          setLoading(false);
        }, 0);
      })
      .catch(err => {
        console.error(err);
        setTimeout(() => {
          setError(true);
          setLoading(false);
        }, 0);
      });
  }

  function retry() {
    setLoading(true);
    setError(false);
    load();
  }

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) { router.push("/login"); return; }
    load();
  }, [router]);

  const completedCount = plans.filter(p => ["completed", "COMPLETED"].includes(p.status)).length;
  const totalLocations = plans.reduce((a, p) => a + (p.locations_count || 0), 0);

  if (loading) {
    return (
      <div className="min-h-screen bg-bg flex items-center justify-center">
        <Loader2 className="w-8 h-8 text-accent-text animate-spin" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-bg">
        <Navbar />
        <div className="pt-32 pb-20 px-6 max-w-screen-xl mx-auto flex flex-col items-center justify-center gap-4 text-center">
          <AlertTriangle className="w-10 h-10 text-destructive" />
          <h2 className="font-display text-2xl font-black tracking-tight text-text">Gezileriniz yüklenemedi</h2>
          <p className="text-text-secondary text-sm max-w-sm">Sunucuya ulaşılamadı. İnternet bağlantınızı kontrol edip tekrar deneyin.</p>
          <Button onClick={retry}>
            <RotateCcw className="w-4 h-4" /> Tekrar Dene
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-bg pb-24">
      <Navbar />

      <div className="pt-28 px-4 md:px-8 max-w-6xl mx-auto">

        {/* ── Başlık ─────────────────────────────────────────────────── */}
        <motion.header
          initial={{ opacity: 0, y: -16 }} animate={{ opacity: 1, y: 0 }}
          className="flex items-center justify-between mb-8"
        >
          <div>
            <p className="font-mono text-xs text-text-tertiary tracking-widest uppercase mb-1">Dashboard</p>
            <h1 className="font-display font-black text-3xl text-text">
              Hoş geldin, <span className="text-accent-text">{username}</span>
            </h1>
          </div>
          <Button
            variant="ghost" size="sm"
            onClick={logout}
            className="hover:text-destructive font-medium"
          >
            <LogOut className="w-4 h-4" />
            <span className="hidden sm:block">Çıkış</span>
          </Button>
        </motion.header>

        {/* ── Kendi istatistiklerim ─────────────────────────────────── */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-8">
          {[
            { label: "Toplam Video", value: plans.length, icon: Video },
            { label: "Tamamlanan", value: completedCount, icon: CheckCircle2 },
            { label: "Toplam Mekan", value: totalLocations, icon: MapPin },
            { label: "Platform Kullanıcı", value: stats?.total_users ?? "—", icon: Globe2 },
          ].map((s, i) => (
            <motion.div key={i} custom={i} variants={cardVariants} initial="hidden" animate="visible">
              <Card className="rounded-md p-4 flex items-center gap-3">
                <s.icon className="w-5 h-5 text-text-tertiary shrink-0" />
                <div>
                  <p className="font-mono text-xl font-semibold text-text tabular-nums">{s.value}</p>
                  <p className="text-[10px] text-text-tertiary uppercase tracking-wider">{s.label}</p>
                </div>
              </Card>
            </motion.div>
          ))}
        </div>

        {/* ── Gezi listesi ──────────────────────────────────────────── */}
        <section>
          <div className="flex items-center justify-between mb-5">
            <h2 className="font-display font-bold text-xl text-text">Gezi Geçmişim</h2>
            <span className="text-xs text-text-tertiary">{plans.length} video</span>
          </div>

          {plans.length === 0 ? (
            <div className="text-center py-20 rounded-lg border border-border-strong border-dashed">
              <div className="text-5xl mb-4">🗺️</div>
              <p className="text-text font-semibold mb-2">Henüz video analiz edilmedi</p>
              <p className="text-text-secondary text-sm mb-5">İlk gezini oluşturmak için bir video yükle.</p>
              <Link href="/upload" className={buttonVariants({ size: "md" })}>
                Video Yükle
              </Link>
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {plans.map((plan, i) => (
                <TripCard key={plan.id} plan={plan} index={i} />
              ))}
              <Link href="/upload"
                className="rounded-lg border border-border-strong border-dashed flex flex-col items-center justify-center gap-2 text-text-tertiary hover:text-text hover:border-accent/40 transition-colors min-h-[168px]">
                <Plus className="w-5 h-5" />
                <span className="text-sm font-medium">Yeni gezi paylaş</span>
              </Link>
            </div>
          )}
        </section>

      </div>
    </div>
  );
}
