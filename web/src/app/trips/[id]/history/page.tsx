"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { ArrowLeft, Calendar, MapPin, AlertTriangle, Loader2, RotateCcw, ChevronRight, Trash2, Clock } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import Navbar from "@/components/Navbar";
import { getItineraries, deleteItinerary, type ItinerarySummary } from "@/lib/api";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { ConfirmDialog } from "@/components/ConfirmDialog";

function scoreColor(score: number): string {
  if (score >= 80) return "text-success";
  if (score >= 50) return "text-warning";
  return "text-destructive";
}

/**
 * Optimizasyon Geçmişi — iOS'un `ItineraryHistoryView`'ıyla AYNI semantik:
 * en yeniden eskiye, açmak yalnızca `GET /itineraries/{id}` çağırır (optimize
 * ASLA tekrar çalıştırılmaz), silme onay gerektirir ve başarılı silme
 * yalnızca ilgili satırı yerel olarak listeden çıkarır (Req 4/12 "do not
 * reload the entire page unnecessarily").
 */
export default function ItineraryHistoryPage() {
  const params = useParams();
  const router = useRouter();
  const tripId = Number(params.id);

  const [itineraries, setItineraries] = useState<ItinerarySummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [pendingDelete, setPendingDelete] = useState<ItinerarySummary | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState("");

  function load() {
    setLoading(true);
    setError("");
    getItineraries(tripId)
      .then((res) => { setItineraries(res.itineraries); setLoading(false); })
      .catch((e) => { setError(e instanceof Error ? e.message : "Yüklenemedi."); setLoading(false); });
  }

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) { router.push("/login"); return; }
    if (!tripId || isNaN(tripId)) {
      setTimeout(() => { setError("Geçersiz gezi ID'si."); setLoading(false); }, 0);
      return;
    }
    setTimeout(() => load(), 0);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tripId, router]);

  async function handleDelete() {
    if (!pendingDelete || deleting) return; // aynı-tık aralığında çift-tıklama koruması
    setDeleting(true);
    setDeleteError("");
    try {
      await deleteItinerary(pendingDelete.id);
      setItineraries((prev) => prev.filter((it) => it.id !== pendingDelete.id));
      setPendingDelete(null);
    } catch (e) {
      setDeleteError(e instanceof Error ? e.message : "Silinemedi.");
    } finally {
      setDeleting(false);
    }
  }

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
          <h2 className="font-display text-2xl font-black tracking-tight text-text">Yüklenemedi</h2>
          <p className="text-text-secondary text-sm max-w-sm">{error}</p>
          <Button onClick={load}><RotateCcw className="w-4 h-4" /> Tekrar Dene</Button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-bg pb-24">
      <Navbar />
      <div className="pt-28 px-4 md:px-8 max-w-3xl mx-auto">
        <button
          onClick={() => router.push(`/trips/${tripId}`)}
          className="flex items-center gap-2 text-text-tertiary hover:text-text transition-all text-[11px] font-bold uppercase tracking-widest mb-6"
        >
          <ArrowLeft className="w-3.5 h-3.5" /> Geziye Dön
        </button>

        <motion.h1
          initial={{ opacity: 0, y: -16 }} animate={{ opacity: 1, y: 0 }}
          className="font-display font-black text-3xl text-text mb-8"
        >
          Optimizasyon Geçmişi
        </motion.h1>

        {itineraries.length === 0 ? (
          <div className="text-center py-16 rounded-lg border border-border-strong border-dashed">
            <Clock className="w-8 h-8 text-text-tertiary mx-auto mb-3" />
            <p className="text-text font-semibold mb-1">Henüz optimizasyon geçmişi yok</p>
            <p className="text-text-secondary text-sm">&quot;Optimize Et&quot; ile ilk itinerary&apos;ini oluştur.</p>
          </div>
        ) : (
          <div className="space-y-3">
            {itineraries.map((it) => (
              <Card key={it.id} className="p-4 flex items-center gap-4">
                <Link
                  href={`/trips/${tripId}/optimize?itineraryId=${it.id}`}
                  className="flex items-center gap-4 flex-1 min-w-0 group"
                >
                  <div className={`w-12 h-12 rounded-full bg-surface2 border border-border flex items-center justify-center font-bold shrink-0 ${scoreColor(it.optimization_score)}`}>
                    {Math.round(it.optimization_score)}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-3 text-xs text-text-secondary flex-wrap">
                      <span className="flex items-center gap-1"><Calendar className="w-3 h-3" /> {it.days_count} gün</span>
                      <span className="flex items-center gap-1"><MapPin className="w-3 h-3" /> {it.stops_count} durak</span>
                      {it.warnings.length > 0 && (
                        <Badge variant="warning">{it.warnings.length} uyarı</Badge>
                      )}
                    </div>
                    {it.created_at && (
                      <p className="text-xs text-text-tertiary mt-1">
                        {new Date(it.created_at).toLocaleDateString("tr-TR", { day: "numeric", month: "long", year: "numeric" })}
                      </p>
                    )}
                  </div>
                  <ChevronRight className="w-4 h-4 text-text-tertiary group-hover:text-text shrink-0" />
                </Link>
                <button
                  aria-label="İtinerary'i sil"
                  onClick={() => setPendingDelete(it)}
                  className="w-9 h-9 rounded-md flex items-center justify-center text-text-tertiary hover:text-destructive hover:bg-destructive/10 transition-colors shrink-0"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </Card>
            ))}
          </div>
        )}
      </div>

      <ConfirmDialog
        open={pendingDelete != null}
        title="Bu optimizasyon geçmişini silmek istediğine emin misin?"
        message="Bu işlem geri alınamaz."
        confirmLabel="Sil"
        destructive
        busy={deleting}
        onConfirm={handleDelete}
        onCancel={() => setPendingDelete(null)}
      />

      {deleteError && (
        <div role="alert" className="fixed bottom-6 right-6 z-[2000] bg-destructive text-bg px-5 py-3 rounded-full text-xs font-bold shadow-lg">
          {deleteError}
        </div>
      )}
    </div>
  );
}
