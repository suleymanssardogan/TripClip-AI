"use client";

import { Suspense, useEffect, useState } from "react";
import { ArrowLeft, Loader2, AlertTriangle, RotateCcw } from "lucide-react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import Navbar from "@/components/Navbar";
import {
  getTrip, getItinerary, optimizeTrip,
  type TripDetail, type Itinerary, type OptimizeTripRequest,
} from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { OptimizerConfigForm } from "@/components/optimizer/OptimizerConfigForm";
import { OptimizerResult } from "@/components/optimizer/OptimizerResult";

/**
 * AI Trip Optimizer — yapılandırma + sonuç, TEK sayfa/route. iOS'un
 * `TripOptimizerConfigView` → `NavigationLink` → `TripOptimizerView`
 * push zincirinin web karşılığı, ama iki AYRI route yerine TEK route +
 * yerel state (Req 7 "should feel native to the existing web application",
 * "do not blindly copy the iOS layout") — bir plan yapılandırmasını
 * (place_ids dizisi dahil) URL'e serileştirmek gereksiz karmaşıklık
 * katardı.
 *
 * `?itineraryId=` parametresi iOS'un `.viewSaved` modunun eşdeğeri:
 * VARSA yapılandırma adımı tamamen ATLANIR, `GET /itineraries/{id}` ile
 * doğrudan sonuç gösterilir — optimize ASLA tekrar ÇALIŞTIRILMAZ (Req 10
 * "Loading a saved itinerary must call the GET itinerary endpoint only").
 *
 * `useSearchParams` yalnızca bu iç bileşende kullanılıyor ve bir
 * `<Suspense>` sınırı içine alınıyor — bkz. Next.js'in kendi
 * "Missing Suspense boundary with useSearchParams" production-build
 * gereksinimi (node_modules/next/dist/docs/.../use-search-params.md).
 */
export default function OptimizePage() {
  return (
    <Suspense fallback={<LoadingShell />}>
      <OptimizePageInner />
    </Suspense>
  );
}

function LoadingShell() {
  return (
    <div className="min-h-screen bg-bg flex items-center justify-center">
      <Loader2 className="w-8 h-8 text-accent-text animate-spin" aria-label="Yükleniyor" />
    </div>
  );
}

function OptimizePageInner() {
  const params = useParams();
  const searchParams = useSearchParams();
  const router = useRouter();
  const tripId = Number(params.id);
  const itineraryIdParam = searchParams.get("itineraryId");
  const savedItineraryId = itineraryIdParam ? Number(itineraryIdParam) : null;

  const [trip, setTrip] = useState<TripDetail | null>(null);
  const [itinerary, setItinerary] = useState<Itinerary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [generating, setGenerating] = useState(false);
  const [generateError, setGenerateError] = useState("");

  function load() {
    if (!tripId || isNaN(tripId)) {
      setError("Geçersiz gezi ID'si.");
      setLoading(false);
      return;
    }
    setLoading(true);
    setError("");

    const loadTrip = getTrip(tripId);
    if (savedItineraryId) {
      // Saved mode: yapılandırma ekranına hiç gerek yok, itinerary'i
      // doğrudan çek — optimize ASLA çağrılmaz.
      Promise.all([loadTrip, getItinerary(savedItineraryId)])
        .then(([t, it]) => { setTrip(t); setItinerary(it); setLoading(false); })
        .catch((e) => { setError(e instanceof Error ? e.message : "Yüklenemedi."); setLoading(false); });
    } else {
      loadTrip
        .then((t) => { setTrip(t); setLoading(false); })
        .catch((e) => { setError(e instanceof Error ? e.message : "Gezi yüklenemedi."); setLoading(false); });
    }
  }

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) { router.push("/login"); return; }
    setTimeout(() => load(), 0);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tripId, savedItineraryId, router]);

  async function handleGenerate(config: OptimizeTripRequest) {
    if (generating) return; // çift-tıklama/yeniden-giriş koruması (Req 6)
    setGenerating(true);
    setGenerateError("");
    try {
      const result = await optimizeTrip(tripId, config);
      setItinerary(result);
    } catch (e) {
      setGenerateError(e instanceof Error ? e.message : "Optimize edilemedi.");
    } finally {
      setGenerating(false);
    }
  }

  if (loading) return <LoadingShell />;

  if (error || !trip) {
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

  const allStops = trip.days.flat();

  return (
    <div className="min-h-screen bg-bg pb-24">
      <Navbar />
      <div className="pt-28 px-4 md:px-8 max-w-3xl mx-auto">
        <button
          onClick={() => router.push(`/trips/${tripId}`)}
          className="flex items-center gap-2 text-text-tertiary hover:text-text transition-all text-[11px] font-bold uppercase tracking-widest mb-6"
        >
          <ArrowLeft className="w-3.5 h-3.5" /> {trip.title}
        </button>

        <h1 className="font-display font-black text-3xl text-text mb-8">
          {itinerary ? (savedItineraryId ? "Kayıtlı İtinerary" : "Optimizasyon Sonucu") : "Gezi Optimizasyonu"}
        </h1>

        {itinerary ? (
          <OptimizerResult
            itinerary={itinerary}
            mode={savedItineraryId ? "saved" : "generate"}
            onApplied={() => { /* Trip detail bir sonraki ziyarette zaten taze veri çeker */ }}
          />
        ) : allStops.length === 0 ? (
          <div className="text-center py-16 rounded-lg border border-border-strong border-dashed">
            <p className="text-text-secondary text-sm">Bu gezide optimize edilecek durak yok.</p>
          </div>
        ) : (
          <>
            <OptimizerConfigForm stops={allStops} submitting={generating} onSubmit={handleGenerate} />
            {generateError && (
              <p role="alert" className="mt-4 text-sm font-semibold text-destructive text-center">{generateError}</p>
            )}
          </>
        )}
      </div>
    </div>
  );
}
