"use client";

import { useMemo, useState } from "react";
import { Minus, Plus, Sparkles } from "lucide-react";
import type { OptimizeTripRequest, TripStop } from "@/lib/api";
import { PlacesSelector } from "./PlacesSelector";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";

// iOS'un TripOptimizerConfigViewModel.durationRange (1...30) ile AYNI —
// backend yalnızca duration_days >= 1 zorunlu kılıyor, üst sınır salt bir
// istemci UI kararı (bkz. o tipin kendi doc yorumu); platformlar arası
// tutarlılık için AYNI değer burada da kullanıldı, yeni bir aralık İCAT
// EDİLMEDİ.
const DURATION_MIN = 1;
const DURATION_MAX = 30;

const DEFAULT_START_TIME = "09:00";
const DEFAULT_END_TIME = "18:00";

interface Props {
  stops: TripStop[];
  submitting: boolean;
  onSubmit: (config: OptimizeTripRequest) => void;
}

/**
 * AI Trip Optimizer yapılandırma formu — iOS'un `TripOptimizerConfigView`'ının
 * web karşılığı, pixel-pixel kopyalanmadan (bkz. Req 7 "should feel native
 * to the existing web application") AYNI alanlar/varsayılanlar/doğrulama
 * kurallarıyla: place seçimi (varsayılan: TÜMÜ), süre (1-30/Otomatik),
 * planlama tarihi (opsiyonel), planlama saatleri (gece yarısını aşan
 * aralıklar DAHİL geçerli — yalnızca EŞİT değerler reddedilir, backend'in
 * kendi TEK doğrulama kuralıyla birebir aynı).
 *
 * Taşıma modu (automobile/walking/transit) BİLEREK burada YOK — bkz.
 * docs/trip-optimizer-bff.md "Web AI Trip Optimizer": `OptimizeTripRequest`
 * hiçbir zaman bir transport_mode alanı taşımadı (iOS'ta bile bu SALT
 * istemci tarafı bir harita gösterim tercihi, backend'e hiç gönderilmiyor),
 * ve web'in kendi haritası (bkz. OptimizerRouteMap.tsx) zaten yalnızca düz
 * çizgi çiziyor — mod başına gerçek rota hesaplamayan bir seçici eklemek
 * kullanıcıyı YANILTIRDI.
 */
export function OptimizerConfigForm({ stops, submitting, onSubmit }: Props) {
  const [selectedIds, setSelectedIds] = useState<Set<number>>(() => new Set(stops.map((s) => s.place_id)));
  const [durationDays, setDurationDays] = useState<number | null>(null);
  const [startTime, setStartTime] = useState(DEFAULT_START_TIME);
  const [endTime, setEndTime] = useState(DEFAULT_END_TIME);
  const [dateEnabled, setDateEnabled] = useState(false);
  const [startDate, setStartDate] = useState<string>(() => new Date().toISOString().slice(0, 10));

  const isTimeRangeValid = startTime !== endTime;
  const canOptimize = selectedIds.size > 0 && isTimeRangeValid && !submitting;

  const orderedSelectedIds = useMemo(
    () => stops.map((s) => s.place_id).filter((id) => selectedIds.has(id)),
    [stops, selectedIds]
  );

  function toggle(placeId: number) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(placeId)) next.delete(placeId); else next.add(placeId);
      return next;
    });
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!canOptimize) return;
    onSubmit({
      selected_place_ids: orderedSelectedIds,
      duration_days: durationDays,
      preferred_start_time: startTime,
      preferred_end_time: endTime,
      start_date: dateEnabled ? startDate : null,
    });
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-8">
      <PlacesSelector
        stops={stops}
        selectedIds={selectedIds}
        onToggle={toggle}
        onSelectAll={() => setSelectedIds(new Set(stops.map((s) => s.place_id)))}
        onDeselectAll={() => setSelectedIds(new Set())}
      />

      {/* Süre */}
      <div className="space-y-3">
        <h3 className="text-[11px] font-bold uppercase tracking-widest text-text-tertiary">Kaç Gün?</h3>
        <Card className="flex items-center justify-between p-4">
          <button
            type="button"
            aria-label="Süreyi azalt"
            onClick={() => setDurationDays((d) => (d == null ? null : d > DURATION_MIN ? d - 1 : null))}
            className="w-9 h-9 rounded-full bg-surface2 hover:bg-border flex items-center justify-center text-text transition-colors"
          >
            <Minus className="w-4 h-4" />
          </button>
          <div className="text-center">
            <p className="font-bold text-text text-lg tabular-nums">{durationDays ?? "Otomatik"}</p>
            <p className="text-[11px] text-text-tertiary">{durationDays == null ? "gün sayısı kendiliğinden hesaplanır" : "gün"}</p>
          </div>
          <button
            type="button"
            aria-label="Süreyi artır"
            onClick={() => setDurationDays((d) => Math.min((d ?? 0) + 1, DURATION_MAX))}
            className="w-9 h-9 rounded-full bg-surface2 hover:bg-border flex items-center justify-center text-text transition-colors"
          >
            <Plus className="w-4 h-4" />
          </button>
        </Card>
      </div>

      {/* Planlama tarihi */}
      <div className="space-y-3">
        <h3 className="text-[11px] font-bold uppercase tracking-widest text-text-tertiary">Planlama Tarihi</h3>
        <Card className="p-4 space-y-3">
          <label className="flex items-center justify-between cursor-pointer">
            <span className="text-sm text-text">{dateEnabled ? "Belirli bir tarih" : "Tarih belirtilmedi"}</span>
            <input
              type="checkbox"
              checked={dateEnabled}
              onChange={(e) => setDateEnabled(e.target.checked)}
              className="w-5 h-5 accent-accent"
              aria-label="Planlama tarihini etkinleştir"
            />
          </label>
          {dateEnabled && (
            <Input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              aria-label="Planlama tarihi"
            />
          )}
        </Card>
        <p className="text-xs text-text-tertiary">
          {dateEnabled
            ? "Günler bu tarihten itibaren gerçek takvim günleri olarak gösterilir."
            : "Belirtilmezse günler yalnızca sıra numarasıyla gösterilir (1. Gün, 2. Gün, …)."}
        </p>
      </div>

      {/* Planlama saatleri */}
      <div className="space-y-3">
        <h3 className="text-[11px] font-bold uppercase tracking-widest text-text-tertiary">Planlama Saatleri</h3>
        <Card className="p-4 grid grid-cols-2 gap-4">
          <label className="space-y-1.5">
            <span className="text-xs text-text-secondary">Başlangıç Saati</span>
            <Input type="time" value={startTime} onChange={(e) => setStartTime(e.target.value)} required />
          </label>
          <label className="space-y-1.5">
            <span className="text-xs text-text-secondary">Bitiş Saati</span>
            <Input type="time" value={endTime} onChange={(e) => setEndTime(e.target.value)} required />
          </label>
        </Card>
        {isTimeRangeValid ? (
          <p className="text-xs text-text-tertiary">
            Optimizer günlük planı bu saat aralığına sığdırır — gece yarısını aşan aralıklar
            (ör. 18:00 → 01:00) da desteklenir. Mekanların kendi açılış saatleri ayrıca dikkate alınır.
          </p>
        ) : (
          <p className="text-xs font-semibold text-destructive">Başlangıç ve bitiş saati aynı olamaz.</p>
        )}
      </div>

      <div className="sticky bottom-4">
        <Card className="p-4 flex items-center justify-between gap-4 shadow-lg">
          <span className={`min-w-0 text-sm font-semibold ${canOptimize ? "text-text" : "text-destructive"}`}>
            {selectedIds.size === 0
              ? "En az bir mekan seçmelisin"
              : !isTimeRangeValid
                ? "Başlangıç saati bitiş saatinden farklı olmalı"
                : `${selectedIds.size} mekan seçildi`}
          </span>
          <Button type="submit" disabled={!canOptimize} className="shrink-0">
            <Sparkles className="w-4 h-4" /> {submitting ? "Optimize ediliyor…" : "Optimize Et"}
          </Button>
        </Card>
      </div>
    </form>
  );
}
