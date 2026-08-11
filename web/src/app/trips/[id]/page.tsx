"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import {
  ArrowLeft, MapPin, Loader2, AlertTriangle, RotateCcw,
  Sparkles, History, Undo2,
} from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import Navbar from "@/components/Navbar";
import { getTrip, type TripDetail } from "@/lib/api";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";

export default function TripDetailPage() {
  const params = useParams();
  const router = useRouter();
  const tripId = Number(params.id);

  const [trip, setTrip] = useState<TripDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  function load() {
    if (!tripId || isNaN(tripId)) {
      setError("Geçersiz gezi ID'si.");
      setLoading(false);
      return;
    }
    setLoading(true);
    setError("");
    getTrip(tripId)
      .then((res) => { setTrip(res); setLoading(false); })
      .catch((e) => { setError(e instanceof Error ? e.message : "Gezi yüklenemedi."); setLoading(false); });
  }

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) { router.push("/login"); return; }
    setTimeout(() => load(), 0);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tripId, router]);

  if (loading) {
    return (
      <div className="min-h-screen bg-bg flex items-center justify-center">
        <Loader2 className="w-8 h-8 text-accent-text animate-spin" aria-label="Yükleniyor" />
      </div>
    );
  }

  if (error || !trip) {
    return (
      <div className="min-h-screen bg-bg">
        <Navbar />
        <div className="pt-32 pb-20 px-6 max-w-screen-xl mx-auto flex flex-col items-center justify-center gap-4 text-center">
          <AlertTriangle className="w-10 h-10 text-destructive" />
          <h2 className="font-display text-2xl font-black tracking-tight text-text">Gezi yüklenemedi</h2>
          <p className="text-text-secondary text-sm max-w-sm">{error}</p>
          <Button onClick={load}><RotateCcw className="w-4 h-4" /> Tekrar Dene</Button>
        </div>
      </div>
    );
  }

  const canEdit = trip.your_role === "owner" || trip.your_role === "editor";

  return (
    <div className="min-h-screen bg-bg pb-24">
      <Navbar />
      <div className="pt-28 px-4 md:px-8 max-w-4xl mx-auto">
        <button
          onClick={() => router.push("/trips")}
          className="flex items-center gap-2 text-text-tertiary hover:text-text transition-all text-[11px] font-bold uppercase tracking-widest mb-6"
        >
          <ArrowLeft className="w-3.5 h-3.5" /> Gezilerim
        </button>

        <motion.header
          initial={{ opacity: 0, y: -16 }} animate={{ opacity: 1, y: 0 }}
          className="flex flex-wrap items-start justify-between gap-4 mb-8"
        >
          <div>
            <h1 className="font-display font-black text-3xl text-text mb-2">{trip.title}</h1>
            <div className="flex items-center gap-3 text-xs text-text-tertiary flex-wrap">
              <span className="flex items-center gap-1"><MapPin className="w-3.5 h-3.5" /> {trip.stops_count} durak</span>
              {trip.total_distance_km != null && <span>{trip.total_distance_km.toFixed(1)} km</span>}
              <Badge variant="neutral">{trip.your_role === "owner" ? "Sahip" : trip.your_role === "editor" ? "Editör" : "İzleyici"}</Badge>
            </div>
          </div>

          {canEdit && (
            <Link href={`/trips/${trip.id}/optimize`}>
              <Button>
                <Sparkles className="w-4 h-4" /> Optimize Et
              </Button>
            </Link>
          )}
        </motion.header>

        {/* Optimizer geçmişi girişleri — herkes görebilir (bkz. core-api'nin
           kendi list_itineraries/list_apply_history erişim kapsamı: viewer
           dahil ERİŞİMİ olan herkes okuyabilir, yalnızca mutasyonlar
           owner/editor gerektirir). */}
        <div className="flex flex-wrap gap-3 mb-8">
          <Link href={`/trips/${trip.id}/history`}>
            <Button variant="outline" size="sm"><History className="w-4 h-4" /> Optimizasyon Geçmişi</Button>
          </Link>
          <Link href={`/trips/${trip.id}/apply-history`}>
            <Button variant="outline" size="sm"><Undo2 className="w-4 h-4" /> Uygulama Geçmişi</Button>
          </Link>
        </div>

        <section>
          <h2 className="font-display font-bold text-xl text-text mb-4">Duraklar</h2>
          {trip.stops_count === 0 ? (
            <div className="text-center py-16 rounded-lg border border-border-strong border-dashed">
              <MapPin className="w-8 h-8 text-text-tertiary mx-auto mb-3" />
              <p className="text-text-secondary text-sm">Bu gezide henüz durak yok.</p>
            </div>
          ) : (
            <div className="space-y-8">
              {trip.days.map((stops, dayIndex) => (
                <div key={dayIndex}>
                  {trip.days.length > 1 && (
                    <h3 className="text-[11px] font-bold uppercase tracking-widest text-text-tertiary mb-3">
                      {dayIndex + 1}. Gün
                    </h3>
                  )}
                  <div className="space-y-2">
                    {stops.map((stop) => (
                      <Card key={`${stop.day_index}-${stop.order_index}-${stop.place_id}`} className="p-4 flex items-center gap-3">
                        <div className="w-8 h-8 rounded-full bg-route/10 border border-route/25 text-route flex items-center justify-center text-xs font-bold shrink-0">
                          {stop.order_index + 1}
                        </div>
                        <div className="min-w-0">
                          <p className="font-semibold text-text text-sm truncate">{stop.name}</p>
                          {(stop.city || stop.category) && (
                            <p className="text-xs text-text-tertiary truncate">
                              {[stop.city, stop.category].filter(Boolean).join(" · ")}
                            </p>
                          )}
                        </div>
                      </Card>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
