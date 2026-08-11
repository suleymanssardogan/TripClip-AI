"use client";
/* eslint-disable @typescript-eslint/no-explicit-any */

import { Fragment, useEffect, useState } from "react";
import { MapPin, AlertTriangle } from "lucide-react";
import "leaflet/dist/leaflet.css";
import type { ItineraryDay, ItineraryStop } from "@/lib/api";

let MapContainer: any, TileLayer: any, Marker: any, Popup: any, Polyline: any, L: any, UseMap: any;

/**
 * iOS'un OptimizerRouteMap.dayColors ile AYNI 5 renk paleti (teal/amber/
 * violet/coral/sky) — platformlar arası görsel tutarlılık için kasıtlı.
 * `MapPreview.tsx`'in kendi tek-renk (#3FD9C4) polyline'ıyla da tutarlı —
 * ilk renk zaten o.
 */
const DAY_COLORS = ["#3FD9C4", "#FFB020", "#AF8AFF", "#FF7474", "#71C6FF"];

/** iOS'un ItineraryStop.id ile AYNI kararlı kimlik biçimi — dizin (array
 * index) DEĞİL, gün+sıra+mekan kimliğinden türetilir (bkz. Req "no array-
 * index identity"). */
export function stopId(stop: ItineraryStop): string {
  return `${stop.day_index}-${stop.order_index}-${stop.place_id ?? "deleted"}`;
}

interface Props {
  days: ItineraryDay[];
  /** `null` = tüm günler aynı anda, kendi renkleriyle. */
  selectedDayIndex: number | null;
  selectedStopId: string | null;
  onSelectStop?: (stop: ItineraryStop) => void;
}

const hasCoords = (s: ItineraryStop) => s.lat != null && s.lng != null;

export type CameraTarget =
  | { type: "point"; coords: [number, number] }
  | { type: "bounds"; coords: [number, number][] }
  | null;

/**
 * Seçimden (gün + durak) kameranın ne yapması gerektiğine karar veren SAF
 * fonksiyon — Leaflet'in kendisine hiç dokunmaz, bu yüzden jsdom'da gerçek
 * bir harita monte etmeden doğrudan test edilebilir (bkz. `stopId()` ile
 * AYNI ilke: karar mantığını render'dan ayır).
 *
 * Öncelik: seçili bir durak varsa VE koordinatı varsa ona odaklan (en
 * spesifik); yoksa seçili günün tüm koordinatlarına sığdır; ne durak ne
 * gün seçiliyse (ör. "Tümü") `null` döner — ilk `center` prop'u zaten ilk
 * yerleşimi hallediyor, burada YENİDEN sığdırmaya gerek yok.
 */
export function computeCameraTarget(
  days: ItineraryDay[], selectedDayIndex: number | null, selectedStopId: string | null
): CameraTarget {
  if (selectedStopId) {
    const stop = days.flatMap((d) => d.stops).find((s) => stopId(s) === selectedStopId);
    if (stop && hasCoords(stop)) {
      return { type: "point", coords: [stop.lat as number, stop.lng as number] };
    }
  }

  if (selectedDayIndex !== null) {
    const day = days.find((d) => d.day_index === selectedDayIndex);
    const coords = (day?.stops ?? []).filter(hasCoords).map((s) => [s.lat as number, s.lng as number] as [number, number]);
    if (coords.length === 1) return { type: "point", coords: coords[0] };
    if (coords.length > 1) return { type: "bounds", coords };
  }

  return null;
}

/**
 * Seçim değiştiğinde haritayı BİR KEZ kameralar — `useEffect`'in bağımlılık
 * dizisi (`selectedStopId`/`selectedDayIndex`) sayesinde yalnızca bu iki
 * değer GERÇEKTEN değiştiğinde çalışır, her render'da DEĞİL (Req 4 "do not
 * continuously refit the map on React renders" / "avoid... update loops").
 * Kullanıcının kendi manuel pan/zoom'unu asla geri almaz — hiçbir harita
 * hareket olayı dinlenmiyor, veri akışı TEK yönlü (seçim → kamera).
 */
function CameraController({
  days, selectedDayIndex, selectedStopId,
}: { days: ItineraryDay[]; selectedDayIndex: number | null; selectedStopId: string | null }) {
  const map = UseMap();

  useEffect(() => {
    const target = computeCameraTarget(days, selectedDayIndex, selectedStopId);
    if (!target) return;
    if (target.type === "point") {
      map.panTo(target.coords, { animate: true });
    } else {
      map.fitBounds(target.coords, { padding: [40, 40], maxZoom: 15 });
    }
  }, [selectedStopId, selectedDayIndex, days, map]);

  return null;
}

/**
 * Optimizer'ın gün-farkında rota haritası — `MapPreview.tsx`'in kurduğu
 * Leaflet/react-leaflet/dinamik-import desenini izler, ama ÇOK GÜNLÜ ve
 * durak-seçimi farkındadır (iOS'un kendi `OptimizerRouteMap`'iyle AYNI
 * semantik: her gün kendi rengi, günler arasında ASLA çizgi yok).
 *
 * ÖNEMLİ SINIRLAMA (kasıtlı, dokümante edilmiş — bkz.
 * docs/ios-trip-optimizer.md "Web AI Trip Optimizer → Route map"): bu harita
 * yalnızca DÜZ ÇİZGİLER çizer, iOS'un MKDirections tabanlı gerçek yol
 * geometrisinin bir eşdeğeri YOK. Web backend'i (Web BFF) rotalı geometri
 * SUNMUYOR, ve bu proje zaten `MapPreview.tsx`'te AYNI düz-çizgi
 * sınırlamasını taşıyor — burada yeni bir rotalama backend'i İCAT EDİLMEDİ
 * (Req 8'in kendi açık izni: "implement the map using available itinerary
 * coordinates and clearly document the limitation").
 */
export default function OptimizerRouteMap({ days, selectedDayIndex, selectedStopId, onSelectStop }: Props) {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    const initLeaflet = async () => {
      const Leaflet = await import("react-leaflet");
      const LeafletLib = await import("leaflet");
      MapContainer = Leaflet.MapContainer;
      TileLayer = Leaflet.TileLayer;
      Marker = Leaflet.Marker;
      Popup = Leaflet.Popup;
      Polyline = Leaflet.Polyline;
      UseMap = Leaflet.useMap;
      L = LeafletLib.default || LeafletLib;
      setTimeout(() => setMounted(true), 50);
    };
    initLeaflet();
  }, []);

  const visibleDays = selectedDayIndex === null ? days : days.filter((d) => d.day_index === selectedDayIndex);
  const visibleStopsWithCoords = visibleDays.flatMap((d) => d.stops.filter(hasCoords));
  const missingCount = visibleDays.flatMap((d) => d.stops).filter((s) => !hasCoords(s)).length;

  if (visibleStopsWithCoords.length === 0) {
    return (
      <div className="w-full h-full bg-surface2 rounded-md flex flex-col items-center justify-center gap-2 text-text-tertiary">
        <MapPin className="w-6 h-6" />
        <p className="text-xs">Haritada gösterilecek konum yok</p>
      </div>
    );
  }

  if (!mounted || !MapContainer) {
    return <div className="w-full h-full bg-surface2 animate-pulse rounded-md" />;
  }

  const center: [number, number] = [
    visibleStopsWithCoords[0].lat as number,
    visibleStopsWithCoords[0].lng as number,
  ];

  function makeIcon(color: string, selected: boolean, order: number) {
    const size = selected ? 30 : 24;
    return L.divIcon({
      className: "",
      html: `<div role="img" aria-label="${order}. durak" style="background:${color};width:${size}px;height:${size}px;border-radius:50%;display:flex;align-items:center;justify-content:center;color:#0a0a0a;font-weight:700;font-size:11px;border:2px solid ${selected ? "#fff" : "rgba(255,255,255,0.35)"};box-shadow:0 2px 6px rgba(0,0,0,0.4);">${order}</div>`,
      iconSize: [size, size],
      iconAnchor: [size / 2, size / 2],
    });
  }

  return (
    <div className="relative w-full h-full rounded-xl overflow-hidden z-0">
      <MapContainer
        center={center}
        zoom={visibleStopsWithCoords.length > 1 ? 12 : 14}
        scrollWheelZoom
        className="w-full h-full z-0"
      >
        <TileLayer
          attribution='&copy; <a href="https://carto.com/attributions">CARTO</a>'
          url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
        />

        <CameraController days={days} selectedDayIndex={selectedDayIndex} selectedStopId={selectedStopId} />

        {visibleDays.map((day) => {
          const color = DAY_COLORS[day.day_index % DAY_COLORS.length];
          const dayStops = day.stops.filter(hasCoords);
          const coords: [number, number][] = dayStops.map((s) => [s.lat as number, s.lng as number]);

          return (
            <Fragment key={day.day_index}>
              {coords.length > 1 && (
                <Polyline positions={coords} color={color} weight={3} opacity={0.7} />
              )}
              {dayStops.map((stop) => {
                const id = stopId(stop);
                const selected = id === selectedStopId;
                return (
                  <Marker
                    key={id}
                    position={[stop.lat as number, stop.lng as number]}
                    icon={makeIcon(color, selected, stop.order_index + 1)}
                    eventHandlers={{ click: () => onSelectStop?.(stop) }}
                  >
                    <Popup>
                      <div className="p-1">
                        <p className="font-bold text-sm">{stop.order_index + 1}. {stop.name}</p>
                        {days.length > 1 && (
                          <p className="text-xs text-gray-600">{day.day_index + 1}. Gün</p>
                        )}
                      </div>
                    </Popup>
                  </Marker>
                );
              })}
            </Fragment>
          );
        })}
      </MapContainer>

      {missingCount > 0 && (
        <div className="absolute bottom-3 left-3 z-[1000] flex items-center gap-2 bg-bg/90 backdrop-blur px-3 py-2 rounded-md border border-border text-[11px] text-text-secondary">
          <AlertTriangle className="w-3.5 h-3.5 text-text-tertiary shrink-0" />
          {missingCount === 1
            ? "1 durağın konum bilgisi yok, haritada gösterilemiyor."
            : `${missingCount} durağın konum bilgisi yok, haritada gösterilemiyor.`}
        </div>
      )}
    </div>
  );
}
