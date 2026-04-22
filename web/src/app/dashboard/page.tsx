"use client";

import React, { useEffect, useState } from "react";
import Navbar from "@/components/Navbar";
import { motion } from "framer-motion";
import { Map, Clock, CheckCircle2, ChevronRight, Globe2, List, Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { getUserPlans, getStats, type Plan, type PlatformStats } from "@/lib/api";

export default function DashboardPage() {
  const router = useRouter();
  const [plans, setPlans] = useState<Plan[]>([]);
  const [stats, setStats] = useState<PlatformStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [email, setEmail] = useState("");

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) { router.push("/login"); return; }

    const userId = Number(localStorage.getItem("user_id"));
    const userEmail = localStorage.getItem("email") || "";
    setEmail(userEmail);

    Promise.all([getUserPlans(userId), getStats()])
      .then(([userPlansData, statsData]) => {
        setPlans(userPlansData.plans);
        setStats(statsData);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [router]);

  const completedCount = plans.filter(p => p.status === "completed" || p.status === "COMPLETED").length;
  const totalLocations = plans.reduce((acc, p) => acc + (p.locations_count || 0), 0);

  const userStats = [
    { label: "Toplam Video", value: String(plans.length), icon: Map },
    { label: "Keşfedilen Mekan", value: String(totalLocations), icon: List },
    { label: "Platform Şehir", value: String(stats?.total_cities || 0), icon: Globe2 },
  ];

  const logout = () => {
    localStorage.clear();
    router.push("/login");
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-surface flex items-center justify-center">
        <Loader2 className="w-8 h-8 text-primary animate-spin" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-surface pb-20 text-on-surface">
      <Navbar />

      <div className="pt-32 px-6 max-w-7xl mx-auto">
        <header className="flex flex-col md:flex-row md:items-center justify-between gap-6 mb-12">
          <div>
            <h1 className="text-4xl font-bold mb-2">Hoş geldin 👋</h1>
            <p className="text-on-surface-variant">{email}</p>
          </div>
          <button
            onClick={logout}
            className="bg-white/5 border border-white/10 text-on-surface-variant px-6 py-3 rounded-2xl font-bold hover:bg-white/10 transition text-sm"
          >
            Çıkış Yap
          </button>
        </header>

        {/* Platform Stats */}
        {stats && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8 p-6 bg-white/5 rounded-3xl border border-white/10">
            {[
              { label: "Toplam Analiz", value: stats.total_videos },
              { label: "Tamamlanan", value: stats.completed_videos },
              { label: "Kullanıcı", value: stats.total_users },
              { label: "Şehir", value: stats.total_cities },
            ].map((s, i) => (
              <div key={i} className="text-center">
                <p className="text-2xl font-black text-primary">{s.value}</p>
                <p className="text-xs text-on-surface-variant mt-1">{s.label}</p>
              </div>
            ))}
          </div>
        )}

        {/* User Stats */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-12">
          {userStats.map((stat, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.1 }}
              className="bg-white/5 border border-white/10 p-6 rounded-3xl"
            >
              <div className="flex items-center gap-4">
                <div className="w-12 h-12 rounded-2xl bg-primary/10 flex items-center justify-center">
                  <stat.icon className="text-primary w-6 h-6" />
                </div>
                <div>
                  <p className="text-xs text-on-surface-variant uppercase font-bold tracking-wider">{stat.label}</p>
                  <p className="text-2xl font-bold">{stat.value}</p>
                </div>
              </div>
            </motion.div>
          ))}
        </div>

        {/* Trips List */}
        <section>
          <h2 className="text-2xl font-bold mb-6">Gezi Geçmişim</h2>

          {plans.length === 0 ? (
            <div className="text-center py-20 text-on-surface-variant">
              <Map className="w-12 h-12 mx-auto mb-4 opacity-30" />
              <p>Henüz analiz edilmiş video yok.</p>
              <p className="text-sm mt-2">Mobil uygulamadan video yükle.</p>
            </div>
          ) : (
            <div className="space-y-4">
              {plans.map((plan, i) => {
                const isCompleted = plan.status === "completed" || plan.status === "COMPLETED";
                return (
                  <motion.div
                    key={plan.id}
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: i * 0.05 }}
                    onClick={() => isCompleted && router.push(`/analyze/${plan.id}`)}
                    className={`group bg-white/5 border border-white/10 p-5 rounded-3xl flex items-center gap-6 hover:border-primary/30 transition-all ${isCompleted ? "cursor-pointer" : "opacity-60"}`}
                  >
                    {/* Icon */}
                    <div className="w-16 h-16 rounded-2xl bg-primary/10 flex items-center justify-center flex-shrink-0">
                      {isCompleted
                        ? <CheckCircle2 className="w-8 h-8 text-emerald-400" />
                        : <Clock className="w-8 h-8 text-primary animate-spin" />}
                    </div>

                    <div className="flex-1 min-w-0">
                      <h3 className="font-bold truncate">
                        {plan.top_location
                          ? plan.top_location.charAt(0).toUpperCase() + plan.top_location.slice(1) + " Gezisi"
                          : plan.filename}
                      </h3>
                      <div className="flex items-center gap-4 text-xs text-on-surface-variant mt-1">
                        <span className="flex items-center gap-1">
                          <Map className="w-3 h-3" /> {plan.locations_count} lokasyon
                        </span>
                        <span className="flex items-center gap-1">
                          <Clock className="w-3 h-3" />
                          {plan.created_at ? new Date(plan.created_at).toLocaleDateString("tr-TR") : "-"}
                        </span>
                        {plan.ocr_preview?.length > 0 && (
                          <span className="hidden md:block truncate max-w-[200px] opacity-60">
                            {plan.ocr_preview.join(", ")}
                          </span>
                        )}
                      </div>
                    </div>

                    <div className="flex items-center gap-3 pr-2">
                      <span className={`text-[10px] font-bold px-3 py-1 rounded-full uppercase ${isCompleted ? "bg-emerald-500/10 text-emerald-400" : "bg-primary/10 text-primary"}`}>
                        {isCompleted ? "Tamamlandı" : "İşleniyor"}
                      </span>
                      {isCompleted && <ChevronRight className="w-5 h-5 text-on-surface-variant group-hover:text-primary transition-colors" />}
                    </div>
                  </motion.div>
                );
              })}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
