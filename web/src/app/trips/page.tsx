"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { MapPin, ChevronRight, Loader2, AlertTriangle, RotateCcw, Map as MapIcon } from "lucide-react";
import { useRouter } from "next/navigation";
import Navbar from "@/components/Navbar";
import { getTrips, type TripSummary } from "@/lib/api";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";

const cardVariants = {
  hidden: { opacity: 0, y: 20 },
  visible: (i: number) => ({
    opacity: 1, y: 0,
    transition: { delay: Math.min(i, 8) * 0.04, duration: 0.4, ease: "easeOut" as const },
  }),
};

const ROLE_LABELS: Record<string, string> = { owner: "Sahip", editor: "Editör", viewer: "İzleyici" };

function TripCard({ trip, index }: { trip: TripSummary; index: number }) {
  const router = useRouter();
  return (
    <motion.div custom={index} variants={cardVariants} initial="hidden" animate="visible">
      <Card
        hover
        onClick={() => router.push(`/trips/${trip.id}`)}
        className="group cursor-pointer"
        role="link"
        tabIndex={0}
        onKeyDown={(e) => { if (e.key === "Enter") router.push(`/trips/${trip.id}`); }}
        aria-label={`${trip.title} gezisini aç`}
      >
        <div className="h-16 flex items-center justify-center bg-surface2">
          <MapIcon className="w-6 h-6 text-text-tertiary" />
        </div>
        <div className="p-4">
          <div className="flex items-start justify-between gap-2 mb-2">
            <h3 className="font-display font-bold text-text text-sm leading-snug">{trip.title}</h3>
            <Badge variant={trip.role === "owner" ? "route" : "neutral"} className="shrink-0">
              {ROLE_LABELS[trip.role] ?? trip.role}
            </Badge>
          </div>
          <div className="flex items-center gap-3 text-xs text-text-tertiary">
            <span className="flex items-center gap-1">
              <MapPin className="w-3 h-3" />
              {trip.stops_count} durak
            </span>
            <span>
              {trip.created_at ? new Date(trip.created_at).toLocaleDateString("tr-TR") : "—"}
            </span>
          </div>
          <div className="flex items-center gap-1 mt-3 text-xs text-text-secondary group-hover:text-text">
            Detayları gör <ChevronRight className="w-3 h-3" />
          </div>
        </div>
      </Card>
    </motion.div>
  );
}

export default function TripsPage() {
  const router = useRouter();
  const [trips, setTrips] = useState<TripSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  function load() {
    setLoading(true);
    setError(false);
    getTrips()
      .then((res) => {
        setTrips(res.trips);
        setLoading(false);
      })
      .catch((err) => {
        console.error(err);
        setError(true);
        setLoading(false);
      });
  }

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) { router.push("/login"); return; }
    setTimeout(() => load(), 0);
  }, [router]);

  if (loading) {
    return (
      <div className="min-h-screen bg-bg flex items-center justify-center">
        <Loader2 className="w-8 h-8 text-accent-text animate-spin" aria-label="Yükleniyor" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-bg">
        <Navbar />
        <div className="pt-32 pb-20 px-6 max-w-screen-xl mx-auto flex flex-col items-center justify-center gap-4 text-center">
          <AlertTriangle className="w-10 h-10 text-destructive" />
          <h2 className="font-display text-2xl font-black tracking-tight text-text">Geziler yüklenemedi</h2>
          <p className="text-text-secondary text-sm max-w-sm">Sunucuya ulaşılamadı. İnternet bağlantınızı kontrol edip tekrar deneyin.</p>
          <Button onClick={load}>
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
        <motion.header
          initial={{ opacity: 0, y: -16 }} animate={{ opacity: 1, y: 0 }}
          className="mb-8"
        >
          <p className="font-mono text-xs text-text-tertiary tracking-widest uppercase mb-1">Trip Builder</p>
          <h1 className="font-display font-black text-3xl text-text">Gezilerim</h1>
        </motion.header>

        {trips.length === 0 ? (
          <div className="text-center py-20 rounded-lg border border-border-strong border-dashed">
            <div className="text-5xl mb-4">🗺️</div>
            <p className="text-text font-semibold mb-2">Henüz gezi yok</p>
            <p className="text-text-secondary text-sm max-w-sm mx-auto">
              Gezilerini TripClip iOS uygulamasından oluştur — burada görüntüleyip AI ile
              optimize edebilirsin.
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {trips.map((trip, i) => (
              <TripCard key={trip.id} trip={trip} index={i} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
