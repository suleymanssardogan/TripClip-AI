"use client";

import { useEffect, useRef, useState } from "react";
import dynamic from "next/dynamic";
import { AlertTriangle, Check, Clock, MapPin, Route, CheckCircle2 } from "lucide-react";
import type { Itinerary, ItineraryStop } from "@/lib/api";
import { applyItinerary } from "@/lib/api";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { stopId } from "@/components/OptimizerRouteMap";

// Leaflet `window` gerektirir — SSR'da render edilemez, MapPreview.tsx'in
// KENDİ `ssr:false` dinamik import deseniyle AYNI.
const OptimizerRouteMap = dynamic(() => import("@/components/OptimizerRouteMap"), {
  ssr: false,
  loading: () => <div className="w-full h-full bg-surface2 animate-pulse rounded-md" />,
});

function scoreColor(score: number): string {
  if (score >= 80) return "text-success";
  if (score >= 50) return "text-warning";
  return "text-destructive";
}

function scoreBadgeVariant(score: number): "success" | "warning" | "destructive" {
  if (score >= 80) return "success";
  if (score >= 50) return "warning";
  return "destructive";
}

interface Props {
  itinerary: Itinerary;
  /** "generate": az önce üretildi. "saved": geçmişten açıldı. */
  mode: "generate" | "saved";
  onApplied?: () => void;
}

/**
 * AI Trip Optimizer sonuç görünümü — hem yeni üretilmiş (generate) hem
 * kayıtlı (saved) itinerary'ler için AYNI bileşen (bkz. Req 10 "the result
 * screen must support both"). iOS'un `TripOptimizerView`'ıyla AYNI sıralama
 * (Req 7): skor → uyarılar → harita → gün seçici → seçili günün durakları →
 * uygula.
 *
 * Gün/durak/harita seçimi TEK, paylaşılan state olarak burada sahiplenilir
 * (iOS'un `OptimizerSelection` ile AYNI ilke — Req 9 "no second source of
 * truth", "avoid state-update loops"): bir durağa tıklamak hem haritayı hem
 * listeyi günceller, bir markera tıklamak o durağın gününe geçer VE
 * listedeki satırı vurgular — tek yönlü veri akışı (state burada, harita/
 * liste yalnızca OKUR + geri bildirir) döngü riskini yapısal olarak ortadan
 * kaldırır.
 */
export function OptimizerResult({ itinerary, mode, onApplied }: Props) {
  const [selectedDayIndex, setSelectedDayIndex] = useState<number | null>(
    itinerary.days.length > 1 ? null : itinerary.days[0]?.day_index ?? null
  );
  const [selectedStopId, setSelectedStopId] = useState<string | null>(null);
  const stopRowsRef = useRef<HTMLDivElement>(null);

  const [showApplyConfirm, setShowApplyConfirm] = useState(false);
  const [applying, setApplying] = useState(false);
  const [applyError, setApplyError] = useState("");
  const [applySuccess, setApplySuccess] = useState(false);

  function selectStop(stop: ItineraryStop) {
    // Durağın kendi günü zaten seçiliyse bu bir no-op (Req 1 "preserve the
    // current day if it belongs to the current day"); değilse o güne geçer.
    setSelectedDayIndex(stop.day_index);
    setSelectedStopId(stopId(stop));
  }

  function selectDay(dayIndex: number | null) {
    setSelectedDayIndex(dayIndex);
    // Gün değişince, seçili durak yeni günün kapsamında değilse temizlenir
    // (Req 3 "clear the selected stop if it does not belong to the selected
    // day") — hâlâ kapsamdaysa (ör. "Tümü"den o durağın kendi gününe geçmek)
    // seçim BİLEREK korunur.
    setSelectedStopId((prev) => {
      if (prev === null) return prev;
      const scope = dayIndex === null
        ? itinerary.days.flatMap((d) => d.stops)
        : itinerary.days.find((d) => d.day_index === dayIndex)?.stops ?? [];
      return scope.some((s) => stopId(s) === prev) ? prev : null;
    });
  }

  // Harita → liste: bir markera tıklamak ilgili satırı görünüme kaydırır
  // (Req 2 "scroll the row into view where practical"). Liste tıklamasında
  // da tetiklenir ama zaten görünürde olduğu için "nearest" pratikte no-op'a
  // yakındır — döngü riski yok, yalnızca `selectedStopId` DEĞİŞTİĞİNDE çalışır
  // (her render'da değil).
  useEffect(() => {
    if (!selectedStopId || !stopRowsRef.current) return;
    const row = stopRowsRef.current.querySelector(`[data-stop-id="${CSS.escape(selectedStopId)}"]`);
    row?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [selectedStopId]);

  async function handleApply() {
    if (applying) return; // aynı-tık aralığında çift-tıklama koruması (bkz. handleGenerate ile aynı desen)
    setApplying(true);
    setApplyError("");
    try {
      await applyItinerary(itinerary.id);
      setShowApplyConfirm(false);
      setApplySuccess(true);
      onApplied?.();
      setTimeout(() => setApplySuccess(false), 3000);
    } catch (e) {
      setApplyError(e instanceof Error ? e.message : "Uygulanamadı.");
    } finally {
      setApplying(false);
    }
  }

  const visibleDays = selectedDayIndex === null
    ? itinerary.days
    : itinerary.days.filter((d) => d.day_index === selectedDayIndex);

  return (
    <div className="space-y-6">
      {/* Skor + özet */}
      <Card className="p-5 flex flex-wrap items-center gap-6">
        <div className="flex items-center gap-3">
          <div className={`text-3xl font-black tabular-nums ${scoreColor(itinerary.optimization_score)}`}>
            {Math.round(itinerary.optimization_score)}
          </div>
          <div>
            <p className="text-xs text-text-tertiary uppercase tracking-widest">Optimizasyon Skoru</p>
            <Badge variant={scoreBadgeVariant(itinerary.optimization_score)}>
              {itinerary.strategy_name}
            </Badge>
          </div>
        </div>
        <div className="flex items-center gap-2 text-sm text-text-secondary">
          <Route className="w-4 h-4" /> {itinerary.total_distance_km.toFixed(1)} km
        </div>
        <div className="flex items-center gap-2 text-sm text-text-secondary">
          <Clock className="w-4 h-4" /> {Math.round(itinerary.total_travel_time_minutes)} dk yol
        </div>
        {mode === "saved" && (
          <Badge variant="neutral" className="ml-auto">Kayıtlı İtinerary</Badge>
        )}
      </Card>

      {/* Uyarılar */}
      {itinerary.warnings.length > 0 && (
        <div className="space-y-2" role="alert">
          {itinerary.warnings.map((w, i) => (
            <div key={i} className="flex items-start gap-2 bg-warning/10 border border-warning/25 rounded-md p-3 text-sm text-warning">
              <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
              <span>{w}</span>
            </div>
          ))}
        </div>
      )}

      {/* Harita */}
      <div className="h-72 sm:h-96 rounded-xl overflow-hidden border border-border">
        <OptimizerRouteMap
          days={itinerary.days}
          selectedDayIndex={selectedDayIndex}
          selectedStopId={selectedStopId}
          onSelectStop={selectStop}
        />
      </div>

      {/* Gün seçici — yatay kaydırılabilir (Req 14 "make day selectors
         horizontally scrollable" on narrow screens) */}
      {itinerary.days.length > 1 && (
        <div className="flex gap-2 overflow-x-auto pb-1" role="tablist" aria-label="Gün seçici">
          <button
            role="tab"
            aria-selected={selectedDayIndex === null}
            onClick={() => selectDay(null)}
            className={`shrink-0 px-4 py-2 rounded-full text-xs font-bold transition-colors ${
              selectedDayIndex === null ? "bg-accent text-on-accent" : "bg-surface2 text-text-secondary hover:bg-border"
            }`}
          >
            Tümü
          </button>
          {itinerary.days.map((day) => (
            <button
              key={day.day_index}
              role="tab"
              aria-selected={selectedDayIndex === day.day_index}
              onClick={() => selectDay(day.day_index)}
              className={`shrink-0 px-4 py-2 rounded-full text-xs font-bold transition-colors ${
                selectedDayIndex === day.day_index ? "bg-accent text-on-accent" : "bg-surface2 text-text-secondary hover:bg-border"
              }`}
            >
              {day.date
                ? new Date(day.date + "T00:00:00").toLocaleDateString("tr-TR", { day: "numeric", month: "long" })
                : `${day.day_index + 1}. Gün`}
            </button>
          ))}
        </div>
      )}

      {/* Seçili gün(ler)in durakları */}
      <div className="space-y-3" ref={stopRowsRef}>
        {visibleDays.map((day) => (
          <div key={day.day_index} className="space-y-2">
            {selectedDayIndex === null && itinerary.days.length > 1 && (
              <h3 className="text-[11px] font-bold uppercase tracking-widest text-text-tertiary pt-2">
                {day.date
                  ? new Date(day.date + "T00:00:00").toLocaleDateString("tr-TR", { day: "numeric", month: "long" })
                  : `${day.day_index + 1}. Gün`}
              </h3>
            )}
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
                      {stop.arrival_time && <span>{stop.arrival_time}</span>}
                      {stop.lat == null && (
                        <span className="flex items-center gap-1 text-warning">
                          <MapPin className="w-3 h-3" /> konum yok
                        </span>
                      )}
                    </div>
                  </div>
                  {/* Seçim yalnızca renkle değil, bir ikonla da iletilir
                     (Req "selected state is not communicated only through
                     color") — PlacesSelector'ın kendi Check göstergesiyle
                     AYNI desen. */}
                  {selected && <Check className="w-4 h-4 text-accent-text shrink-0" aria-hidden="true" />}
                </Card>
              );
            })}
          </div>
        ))}
      </div>

      {/* Uygula */}
      <Card className="p-4 flex items-center justify-between gap-4 sticky bottom-4 shadow-lg">
        {applySuccess ? (
          <span className="min-w-0 flex items-center gap-2 text-sm font-semibold text-success">
            <CheckCircle2 className="w-4 h-4 shrink-0" /> Gezinin durak listesi güncellendi.
          </span>
        ) : (
          <span className="min-w-0 text-sm text-text-secondary">Bu itinerary gezinin durak listesine uygulanabilir.</span>
        )}
        <Button onClick={() => setShowApplyConfirm(true)} disabled={applying} className="shrink-0">
          Trip&apos;e Uygula
        </Button>
      </Card>

      <ConfirmDialog
        open={showApplyConfirm}
        title="Bu itinerary Trip'e uygulansın mı?"
        message="Gezinin mevcut durak listesi bu itinerary ile değiştirilecek. Kayıtlı itinerary geçmişte kalır ve istediğin zaman tekrar uygulanabilir."
        confirmLabel="Uygula"
        busy={applying}
        onConfirm={handleApply}
        onCancel={() => setShowApplyConfirm(false)}
      />

      {applyError && (
        <div role="alert" className="fixed bottom-6 right-6 z-[2000] bg-destructive text-bg px-5 py-3 rounded-full text-xs font-bold shadow-lg">
          {applyError}
        </div>
      )}
    </div>
  );
}
