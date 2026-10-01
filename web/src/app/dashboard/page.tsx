"use client";

import React, { useCallback, useEffect, useState } from "react";
import { motion } from "framer-motion";
import {
  MapPin, Clock, ChevronRight,
  LogOut, Loader2, AlertTriangle, RotateCcw,
} from "lucide-react";
import { useRouter } from "next/navigation";
import Navbar from "@/components/Navbar";
import { getSession, getUserPlans, getStats, logout, deleteAccount, type Plan, type PlatformStats } from "@/lib/api";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";

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
        onKeyDown={event => { if (isCompleted && (event.key === "Enter" || event.key === " ")) { event.preventDefault(); router.push(`/analyze/${plan.id}`); } }}
        role={isCompleted ? "link" : undefined}
        tabIndex={isCompleted ? 0 : undefined}
        aria-label={isCompleted ? `${title} detaylarını gör` : undefined}
        className={`group ${isCompleted ? "cursor-pointer focus-visible:outline-2 focus-visible:outline-route" : "opacity-70"}`}
      >
        <div className="p-6">
          <p className="mb-4 text-[10px] font-semibold uppercase tracking-[0.16em] text-accent-text">Video planı</p>
          <div className="flex items-start justify-between gap-2 mb-2">
            <h3 className="font-display text-lg font-bold leading-snug tracking-tight text-text">{title}</h3>
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
  const [deleting, setDeleting] = useState(false);
  const username = email.split("@")[0];

  const load = useCallback(async () => {
    const session = await getSession();
    if (!session) { router.push("/login"); return; }
    Promise.all([getUserPlans(session.user_id), getStats()])
      .then(([up, st]) => {
        setTimeout(() => {
          setEmail(session.email);
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
  }, [router]);

  function retry() {
    setLoading(true);
    setError(false);
    load();
  }

  useEffect(() => { load(); }, [load]);

  const completedCount = plans.filter(p => ["completed", "COMPLETED"].includes(p.status)).length;
  const totalLocations = plans.reduce((a, p) => a + (p.locations_count || 0), 0);

  async function handleDeleteAccount() {
    if (!window.confirm("Hesabınız ve tüm verileriniz kalıcı olarak silinecek. Devam edilsin mi?")) return;
    setDeleting(true);
    try { await deleteAccount(); window.location.href = "/"; }
    catch { setDeleting(false); window.alert("Hesap silinemedi. Lütfen tekrar deneyin."); }
  }

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
          <h2 className="font-display text-2xl font-bold tracking-tight text-text">Gezileriniz yüklenemedi</h2>
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

      <div className="mx-auto max-w-7xl px-5 pb-24 pt-28 sm:px-8">

        {/* ── Başlık ─────────────────────────────────────────────────── */}
        <motion.header
          initial={{ opacity: 0, y: -16 }} animate={{ opacity: 1, y: 0 }}
          className="mb-7 flex items-center justify-between"
        >
          <div>
            <p className="mb-2 text-xs font-bold uppercase tracking-[0.2em] text-route">YOLCULUK GÜNLÜĞÜN</p>
            <h1 className="font-display text-3xl font-bold tracking-[-0.05em] text-text sm:text-4xl">
              Merhaba, <span className="text-accent-text">{username}</span>.
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

        <div className="mb-7 rounded-2xl border border-[#dce9f2] bg-[#eef5fa] px-7 py-8 dark:border-border dark:bg-surface sm:px-10 sm:py-10">
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-accent-text">Bir sonraki gezi</p>
          <h2 className="mt-3 max-w-lg font-display text-2xl font-bold leading-tight tracking-[-0.045em] text-text sm:text-3xl">İlham aldığın videolar birer rotaya dönüşsün.</h2>
          <p className="mt-3 max-w-lg text-sm leading-6 text-text-secondary">iOS uygulamasından bir video paylaş veya gezi fikirlerine göz at.</p>
          <button onClick={() => router.push("/explore")} className="mt-6 inline-flex items-center gap-2 rounded-md bg-accent px-5 py-3 text-sm font-semibold text-on-accent hover:bg-accent-hover">Gezileri keşfet <ChevronRight className="h-4 w-4" /></button>
        </div>

        {/* ── Kendi istatistiklerim ─────────────────────────────────── */}
        <div className="mb-8 grid grid-cols-2 gap-3 md:grid-cols-4">
          {[
            { label: "Toplam video", value: plans.length },
            { label: "Tamamlanan", value: completedCount },
            { label: "Toplam mekân", value: totalLocations },
            { label: "Platform kullanıcı", value: stats?.total_users ?? "—" },
          ].map((s, i) => (
            <motion.div key={i} custom={i} variants={cardVariants} initial="hidden" animate="visible">
              <Card className="p-5 sm:p-6">
                <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-text-tertiary">{s.label}</p>
                <p className="mt-3 font-display text-3xl font-bold tabular-nums tracking-tight text-text">{s.value}</p>
              </Card>
            </motion.div>
          ))}
        </div>
        <div className="mb-8 flex justify-end">
          <button onClick={handleDeleteAccount} disabled={deleting} className="text-xs text-destructive hover:underline disabled:opacity-50">
            {deleting ? "Hesap siliniyor…" : "Hesabımı ve verilerimi sil"}
          </button>
        </div>

        {/* ── Gezi listesi ──────────────────────────────────────────── */}
        <section>
          <div className="flex items-center justify-between mb-5">
            <h2 className="font-display text-2xl font-bold tracking-tight text-text">Kaydettiğin yolculuklar</h2>
            <span className="text-xs text-text-tertiary">{plans.length} video</span>
          </div>

          {plans.length === 0 ? (
            <div className="rounded-xl border border-border bg-surface px-6 py-16 text-center">
              <p className="mb-2 font-display text-xl font-bold text-text">İlk yolculuğun burada görünecek</p>
              <p className="text-text-secondary text-sm">
                Bir Instagram Reel&apos;i TripClip iOS uygulamasından paylaşarak başla.
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {plans.map((plan, i) => (
                <TripCard key={plan.id} plan={plan} index={i} />
              ))}
            </div>
          )}
        </section>

      </div>
    </div>
  );
}
