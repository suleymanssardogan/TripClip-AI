"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import dynamic from "next/dynamic";
import { motion } from "framer-motion";
import {
  ArrowLeft, MapPin, Loader2, AlertTriangle, RotateCcw,
  Sparkles, History, Undo2, Check, CheckCircle2, ChevronRight, MessageCircle,
} from "lucide-react";
import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import Navbar from "@/components/Navbar";
import { getTrip, type TripDetail, type TripStop, type ItineraryDay, type ItineraryStop } from "@/lib/api";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { stopId } from "@/components/OptimizerRouteMap";

// Leaflet `window` gerektirir — MapPreview.tsx/OptimizerResult.tsx'in KENDİ
// `ssr:false` dinamik import deseniyle AYNI.
const OptimizerRouteMap = dynamic(() => import("@/components/OptimizerRouteMap"), {
  ssr: false,
  loading: () => <div className="w-full h-full bg-surface2 animate-pulse rounded-md" />,
});

/**
 * Trip'in kendi `days: TripStop[][]`'ını, ZATEN VAR OLAN (Milestone 21-23'te
 * kurulmuş) `OptimizerRouteMap`/`stopId` ile render edebilmek için
 * `ItineraryDay[]`'e çevirir — yeni bir harita/seçim mimarisi İCAT EDİLMEDİ
 * (Req 3 "there is already map/selection infrastructure... do not rebuild
 * it"). Saf, imzasız veriler (arrival_time vb.) `null`/`0` kalır — Trip
 * Detail'ın kendi `TripStop`'unda hiç yok, UYDURULMADI.
 */
function tripDaysToItineraryDays(days: TripStop[][]): ItineraryDay[] {
  return days
    .filter((stops) => stops.length > 0)
    .map((stops) => ({
      day_index: stops[0].day_index,
      date: null,
      stops: stops.map((s) => ({
        place_id: s.place_id, name: s.name, lat: s.lat, lng: s.lng,
        day_index: s.day_index, order_index: s.order_index,
        arrival_time: null, departure_time: null, visit_duration_minutes: 0,
        travel_time_to_next_minutes: null, travel_distance_to_next_km: null,
      })),
    }));
}

/**
 * `useSearchParams` yalnızca bu iç bileşende kullanılıyor ve bir
 * `<Suspense>` sınırı içine alınıyor — bkz. Next.js'in kendi "Missing
 * Suspense boundary with useSearchParams" production-build gereksinimi
 * (optimize/page.tsx'teki AYNI desen).
 */
export default function TripDetailPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen bg-bg flex items-center justify-center">
        <Loader2 className="w-8 h-8 text-accent-text animate-spin" aria-label="Yükleniyor" />
      </div>
    }>
      <TripDetailPageInner />
    </Suspense>
  );
}

function TripDetailPageInner() {
  const params = useParams();
  const router = useRouter();
  const searchParams = useSearchParams();
  const tripId = Number(params.id);

  const [trip, setTrip] = useState<TripDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // Harita ↔ itinerary listesi arasında PAYLAŞILAN tek seçim — OptimizerResult.tsx
  // ile AYNI desen (selectedDayIndex/selectedStopId, aynı selectDay() gün-
  // kapsamı temizleme kuralı) — yeni bir seçim mimarisi İCAT EDİLMEDİ.
  //
  // AI Asistan bir durağa referans verdiğinde (`?focusDay=&focusPlace=`)
  // buraya döner ve o durağı SEÇİLİ başlatır (bkz. Req 8 "the UI should be
  // capable of identifying that stop without parsing the text") — kimlik
  // yine `stopId()`'in AYNI (day_index, place_id) formülüyle KURULUR,
  // metin/asistan cevabı ASLA ayrıştırılmaz.
  const focusDayParam = searchParams.get("focusDay");
  const focusPlaceParam = searchParams.get("focusPlace");
  const [selectedDayIndex, setSelectedDayIndex] = useState<number | null>(null);
  const [selectedStopId, setSelectedStopId] = useState<string | null>(null);
  const stopRowsRef = useRef<HTMLDivElement>(null);

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

  // Harita bir markera GERÇEKTEN tıklandığında (bkz. `OptimizerRouteMap`'in
  // kendi `computeCameraTarget`/`CameraController`'ı, Milestone 23) ilgili
  // satırı görünüme kaydırır — `OptimizerResult.tsx`'teki AYNI mantık.
  useEffect(() => {
    if (!selectedStopId || !stopRowsRef.current) return;
    const row = stopRowsRef.current.querySelector(`[data-stop-id="${CSS.escape(selectedStopId)}"]`);
    row?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [selectedStopId]);

  function selectStop(stop: ItineraryStop) {
    setSelectedDayIndex(stop.day_index);
    setSelectedStopId(stopId(stop));
  }

  function selectDay(dayIndex: number | null, days: ItineraryDay[]) {
    setSelectedDayIndex(dayIndex);
    setSelectedStopId((prev) => {
      if (prev === null) return prev;
      const scope = dayIndex === null ? days.flatMap((d) => d.stops) : (days.find((d) => d.day_index === dayIndex)?.stops ?? []);
      return scope.some((s) => stopId(s) === prev) ? prev : null;
    });
  }

  // AI Asistan'dan `?focusDay=&focusPlace=` ile dönüldüğünde, trip
  // yüklendikten SONRA gerçek durağı bulup `selectStop()` ile seç —
  // `order_index` URL'de yok, bu yüzden `stopId()` yalnızca trip'in kendi
  // (zaten yüklü) verisinden kurulan GERÇEK durak nesnesiyle çağrılabilir.
  useEffect(() => {
    if (!trip || focusDayParam === null || focusPlaceParam === null) return;
    const dayIndex = Number(focusDayParam);
    const placeId = Number(focusPlaceParam);
    const stop = trip.days.flat().find((s) => s.day_index === dayIndex && s.place_id === placeId);
    if (stop) {
      setTimeout(() => selectStop({
        ...stop, arrival_time: null, departure_time: null, visit_duration_minutes: 0,
        travel_time_to_next_minutes: null, travel_distance_to_next_km: null,
      }), 0);
    }
  }, [trip, focusDayParam, focusPlaceParam]);

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
  const itineraryDays = tripDaysToItineraryDays(trip.days);
  const hasMultipleDays = itineraryDays.length > 1;
  const visibleDays = selectedDayIndex === null
    ? itineraryDays
    : itineraryDays.filter((d) => d.day_index === selectedDayIndex);

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

        {/* Harita — TripStop'lardan zaten koordinatlı olanlar varsa gösterilir.
           `OptimizerRouteMap`'in KENDİ eksik-koordinat/empty-state davranışı
           (Milestone 21) burada da geçerli, yeniden İCAT EDİLMEDİ. */}
        {trip.stops_count > 0 && (
          <div className="h-72 sm:h-96 rounded-xl overflow-hidden border border-border mb-8">
            <OptimizerRouteMap
              days={itineraryDays}
              selectedDayIndex={selectedDayIndex}
              selectedStopId={selectedStopId}
              onSelectStop={selectStop}
            />
          </div>
        )}

        <div className="flex flex-wrap gap-3 mb-8">
          <Link href={`/trips/${trip.id}/assistant`}>
            <Button variant="outline" size="sm"><MessageCircle className="w-4 h-4" /> AI Asistan</Button>
          </Link>
          <Link href={`/trips/${trip.id}/history`}>
            <Button variant="outline" size="sm"><History className="w-4 h-4" /> Optimizasyon Geçmişi</Button>
          </Link>
          <Link href={`/trips/${trip.id}/apply-history`}>
            <Button variant="outline" size="sm"><Undo2 className="w-4 h-4" /> Uygulama Geçmişi</Button>
          </Link>
        </div>

        {/* Uygulanan itinerary göstergesi (Req 8 "apply-state awareness") —
           backend bu alanları zaten gönderiyordu (`TripDetail.applied_itinerary_id`/
           `.itinerary_applied_at`), sayfa şimdiye kadar hiç GÖSTERMİYORDU. Yeni
           bir API çağrısı YOK, salt mevcut state'in sunumu. */}
        {trip.applied_itinerary_id != null && (
          <Link
            href={`/trips/${trip.id}/apply-history`}
            className="flex items-center gap-3 p-3 mb-8 rounded-lg border border-route/20 bg-route/5 hover:bg-route/10 transition-colors"
          >
            <CheckCircle2 className="w-5 h-5 text-route shrink-0" />
            <div className="min-w-0 flex-1">
              <p className="text-sm font-semibold text-text">Bir optimizer itinerary&apos;si uygulandı</p>
              {trip.itinerary_applied_at && (
                <p className="text-xs text-text-secondary">
                  {new Date(trip.itinerary_applied_at).toLocaleString("tr-TR")}
                </p>
              )}
            </div>
            <ChevronRight className="w-4 h-4 text-text-tertiary shrink-0" />
          </Link>
        )}

        <section>
          <h2 className="font-display font-bold text-xl text-text mb-4">Duraklar</h2>

          {trip.stops_count === 0 ? (
            <div className="text-center py-16 rounded-lg border border-border-strong border-dashed">
              <MapPin className="w-8 h-8 text-text-tertiary mx-auto mb-3" />
              <p className="text-text-secondary text-sm">Bu gezide henüz durak yok.</p>
            </div>
          ) : (
            <>
              {hasMultipleDays && (
                <div className="flex gap-2 overflow-x-auto pb-1 mb-4" role="tablist" aria-label="Gün seçici">
                  <button
                    role="tab"
                    aria-selected={selectedDayIndex === null}
                    onClick={() => selectDay(null, itineraryDays)}
                    className={`shrink-0 px-4 py-2 rounded-full text-xs font-bold transition-colors ${
                      selectedDayIndex === null ? "bg-accent text-on-accent" : "bg-surface2 text-text-secondary hover:bg-border"
                    }`}
                  >
                    Tümü
                  </button>
                  {itineraryDays.map((day) => (
                    <button
                      key={day.day_index}
                      role="tab"
                      aria-selected={selectedDayIndex === day.day_index}
                      onClick={() => selectDay(day.day_index, itineraryDays)}
                      className={`shrink-0 px-4 py-2 rounded-full text-xs font-bold transition-colors ${
                        selectedDayIndex === day.day_index ? "bg-accent text-on-accent" : "bg-surface2 text-text-secondary hover:bg-border"
                      }`}
                    >
                      {day.day_index + 1}. Gün
                    </button>
                  ))}
                </div>
              )}

              <div className="space-y-8" ref={stopRowsRef}>
                {visibleDays.map((day) => (
                  <div key={day.day_index}>
                    {hasMultipleDays && selectedDayIndex === null && (
                      <h3 className="text-[11px] font-bold uppercase tracking-widest text-text-tertiary mb-3">
                        {day.day_index + 1}. Gün
                      </h3>
                    )}
                    <div className="space-y-2">
                      {day.stops.map((stop) => {
                        const id = stopId(stop);
                        const selected = id === selectedStopId;
                        return (
                          <Card
                            key={id}
                            data-stop-id={id}
                            className={`p-4 flex items-center gap-3 cursor-pointer transition-colors ${
                              selected ? "border-accent/50 bg-accent/5" : "hover:border-border-strong"
                            }`}
                            role="button"
                            tabIndex={0}
                            aria-pressed={selected}
                            onClick={() => selectStop(stop)}
                            onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); selectStop(stop); } }}
                          >
                            <div className="w-8 h-8 rounded-full bg-route/10 border border-route/25 text-route flex items-center justify-center text-xs font-bold shrink-0">
                              {stop.order_index + 1}
                            </div>
                            <div className="min-w-0 flex-1">
                              <p className="font-semibold text-text text-sm truncate">{stop.name}</p>
                              <div className="flex items-center gap-2 text-xs text-text-tertiary">
                                {(() => {
                                  const original = trip.days.flat().find((s) => s.place_id === stop.place_id);
                                  return original && (original.city || original.category) ? (
                                    <span className="truncate">{[original.city, original.category].filter(Boolean).join(" · ")}</span>
                                  ) : null;
                                })()}
                                {stop.lat == null && (
                                  <span className="flex items-center gap-1 text-warning shrink-0">
                                    <MapPin className="w-3 h-3" /> konum yok
                                  </span>
                                )}
                              </div>
                            </div>
                            {selected && <Check className="w-4 h-4 text-accent-text shrink-0" aria-hidden="true" />}
                          </Card>
                        );
                      })}
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}
        </section>
      </div>
    </div>
  );
}
