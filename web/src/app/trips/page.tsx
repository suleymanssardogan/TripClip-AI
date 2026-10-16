"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { MapPin, ChevronRight, Loader2, AlertTriangle, RotateCcw } from "lucide-react";
import { useRouter } from "next/navigation";
import Navbar from "@/components/Navbar";
import { getSession, getTrips, type TripSummary } from "@/lib/api";
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
        className="group cursor-pointer focus-visible:outline-2 focus-visible:outline-route"
        role="link"
        tabIndex={0}
        onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); router.push(`/trips/${trip.id}`); } }}
        aria-label={`${trip.title} gezisini aç`}
      >
        <div className="p-5">
          <div className="flex items-start justify-between gap-2 mb-2">
            <h3 className="font-display text-lg font-bold leading-snug text-text">{trip.title}</h3>
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
  const [hasMore, setHasMore] = useState(false);
  const [nextOffset, setNextOffset] = useState(0);
  const [loadingMore, setLoadingMore] = useState(false);
  const [pageError, setPageError] = useState(false);

  function load() {
    setLoading(true);
    setError(false);
    getTrips()
      .then((res) => {
        setTrips(res.trips);
        setNextOffset(res.trips.length);
        setHasMore(res.has_more ?? res.trips.length < (res.total ?? res.trips.length));
        setLoading(false);
      })
      .catch((err) => {
        console.error(err);
        setError(true);
        setLoading(false);
      });
  }

  async function loadMore() {
    if (loadingMore || !hasMore) return;
    setLoadingMore(true);
    setPageError(false);
    try {
      const res = await getTrips(20, nextOffset);
      setTrips(current => {
        const ids = new Set(current.map(item => item.id));
        return [...current, ...res.trips.filter(item => !ids.has(item.id))];
      });
      const next = nextOffset + res.trips.length;
      setNextOffset(next);
      setHasMore(res.trips.length > 0 && (res.has_more ?? next < (res.total ?? next)));
    } catch {
      setPageError(true);
    } finally {
      setLoadingMore(false);
    }
  }

  useEffect(() => {
    getSession().then(session => {
      if (!session) router.push("/login");
      else load();
    });
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
          <h2 className="font-display text-2xl font-bold tracking-tight text-text">Geziler yüklenemedi</h2>
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
      <div className="mx-auto max-w-7xl px-5 pt-28 sm:px-8">
        <motion.header
          initial={{ opacity: 0, y: -16 }} animate={{ opacity: 1, y: 0 }}
          className="mb-8"
        >
          <p className="mb-3 text-xs font-bold uppercase tracking-[0.2em] text-accent-text">Yolculukların</p>
          <h1 className="font-display text-[clamp(2.5rem,4.5vw,4rem)] font-bold tracking-[-0.055em] text-text">Gezilerin.</h1>
          <p className="mt-4 max-w-xl text-sm leading-7 text-text-secondary">Kaydettiğin duraklar ve oluşturduğun rotalar bir arada.</p>
        </motion.header>

        {trips.length === 0 ? (
          <div className="rounded-xl border border-border bg-surface px-6 py-16 text-center">
            <p className="mb-2 font-display text-xl font-bold text-text">Henüz gezi yok</p>
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
        {pageError && <p role="alert" className="mt-4 text-sm text-destructive">Yükleme başarısız. Tekrar deneyebilirsin.</p>}
        {hasMore && <div className="mt-6 flex justify-center"><Button onClick={loadMore} disabled={loadingMore}>{loadingMore ? "Yükleniyor…" : "Daha fazla yükle"}</Button></div>}
      </div>
    </div>
  );
}
