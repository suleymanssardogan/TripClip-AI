"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { ArrowLeft, Undo2, Check, AlertTriangle, Loader2, RotateCcw } from "lucide-react";
import { useParams, useRouter } from "next/navigation";
import Navbar from "@/components/Navbar";
import { getApplyHistory, undoApply, ApiError, type ApplyHistoryEntry } from "@/lib/api";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { ConfirmDialog } from "@/components/ConfirmDialog";

function entryTitle(entry: ApplyHistoryEntry): string {
  if (entry.itinerary_id != null) {
    return entry.is_undo ? "Önceki itinerary'e dönüldü" : "Itinerary uygulandı";
  }
  return entry.is_undo ? "Manuel durak listesine dönüldü" : "Silinmiş optimizasyon";
}

/**
 * Uygulama Geçmişi — iOS'un `ItineraryApplyHistoryView`'ıyla AYNI semantik:
 * en yeniden eskiye, yalnızca sunucunun `is_undoable: true` işaretlediği
 * (en son) kayıt "Geri Al" gösterir — bu asla istemci tarafında TÜRETİLMEZ
 * (Req 13 "Only the latest applicable history entry should show Undo").
 *
 * `STALE_UNDO` (409) ele alınışı BİLEREK yerel bir mutasyon DENEMEZ —
 * yalnızca net bir mesaj gösterir ve listeyi SUNUCUDAN yeniden yükler (Req
 * 13'ün kendi açık talimatı: "refresh history rather than attempting
 * another local mutation" — sunucu tek otorite, bkz. `docs/trip-optimizer.md`
 * "Apply History & Undo → Latest-only safety rule").
 */
export default function ApplyHistoryPage() {
  const params = useParams();
  const router = useRouter();
  const tripId = Number(params.id);

  const [entries, setEntries] = useState<ApplyHistoryEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [pendingUndo, setPendingUndo] = useState<ApplyHistoryEntry | null>(null);
  const [undoing, setUndoing] = useState(false);
  const [undoError, setUndoError] = useState("");
  const [undoSuccess, setUndoSuccess] = useState(false);

  function load() {
    setLoading(true);
    setError("");
    getApplyHistory(tripId)
      .then((res) => { setEntries(res.entries); setLoading(false); })
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

  async function handleUndo() {
    if (!pendingUndo || undoing) return; // aynı-tık aralığında çift-tıklama koruması
    setUndoing(true);
    setUndoError("");
    try {
      await undoApply(tripId, pendingUndo.id);
      setPendingUndo(null);
      setUndoSuccess(true);
      setTimeout(() => setUndoSuccess(false), 3000);
      // Sunucu tek otorite — yerel tahmin yok, listeyi baştan yükle (bkz.
      // bileşenin kendi doc yorumu).
      load();
    } catch (e) {
      if (e instanceof ApiError && e.code === "STALE_UNDO") {
        setUndoError("Bu kayıt artık en son değil — başka bir işlem araya girdi. Liste güncellendi.");
        setPendingUndo(null);
        load();
      } else {
        setUndoError(e instanceof Error ? e.message : "Geri alınamadı.");
      }
    } finally {
      setUndoing(false);
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
          Uygulama Geçmişi
        </motion.h1>

        {undoSuccess && (
          <div className="mb-4 flex items-center gap-2 bg-success/10 border border-success/25 text-success rounded-md p-3 text-sm">
            <Check className="w-4 h-4" /> Geri alma işlemi tamamlandı.
          </div>
        )}

        {entries.length === 0 ? (
          <div className="text-center py-16 rounded-lg border border-border-strong border-dashed">
            <Undo2 className="w-8 h-8 text-text-tertiary mx-auto mb-3" />
            <p className="text-text font-semibold mb-1">Henüz uygulama geçmişi yok</p>
            <p className="text-text-secondary text-sm">Bir itinerary&apos;i gezine uyguladığında burada saklanır.</p>
          </div>
        ) : (
          <div className="space-y-3">
            {entries.map((entry) => (
              <Card key={entry.id} className="p-4 flex items-center gap-4">
                <div className={`w-11 h-11 rounded-full flex items-center justify-center shrink-0 ${
                  entry.is_undo ? "bg-warning/10 border border-warning/25 text-warning" : "bg-success/10 border border-success/25 text-success"
                }`}>
                  {entry.is_undo ? <Undo2 className="w-4 h-4" /> : <Check className="w-4 h-4" />}
                </div>
                <div className="min-w-0 flex-1">
                  <p className="font-semibold text-text text-sm">{entryTitle(entry)}</p>
                  <div className="flex items-center gap-2 text-xs text-text-tertiary flex-wrap">
                    <span>{new Date(entry.applied_at).toLocaleString("tr-TR")}</span>
                    {entry.is_undoable && <Badge variant="route">Güncel</Badge>}
                  </div>
                </div>
                {entry.is_undoable && (
                  <Button
                    variant="outline" size="sm"
                    className="border-destructive/40 text-destructive hover:bg-destructive/10 hover:border-destructive/60 shrink-0"
                    onClick={() => setPendingUndo(entry)}
                  >
                    Geri Al
                  </Button>
                )}
              </Card>
            ))}
          </div>
        )}
      </div>

      <ConfirmDialog
        open={pendingUndo != null}
        title="Son optimizasyon uygulamasını geri almak istediğine emin misin?"
        message="Gezinin durak listesi bu geri almadan önceki hâline döner."
        confirmLabel="Geri Al"
        destructive
        busy={undoing}
        onConfirm={handleUndo}
        onCancel={() => setPendingUndo(null)}
      />

      {undoError && (
        <div role="alert" className="fixed bottom-6 right-6 z-[2000] max-w-sm bg-destructive text-bg px-5 py-3 rounded-md text-xs font-bold shadow-lg">
          {undoError}
        </div>
      )}
    </div>
  );
}
