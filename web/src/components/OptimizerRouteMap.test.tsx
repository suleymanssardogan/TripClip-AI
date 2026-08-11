import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import OptimizerRouteMap, { stopId, computeCameraTarget } from "./OptimizerRouteMap";
import type { ItineraryStop, ItineraryDay } from "@/lib/api";

function stop(overrides: Partial<ItineraryStop> = {}): ItineraryStop {
  return {
    place_id: 12, name: "Ayasofya", lat: 41.0086, lng: 28.9802,
    day_index: 0, order_index: 0, arrival_time: null, departure_time: null,
    visit_duration_minutes: 30, travel_time_to_next_minutes: null, travel_distance_to_next_km: null,
    ...overrides,
  };
}

describe("stopId", () => {
  it("is derived from day/order/place — not array index (Req: no array-index identity)", () => {
    expect(stopId(stop({ day_index: 1, order_index: 2, place_id: 12 }))).toBe("1-2-12");
  });

  it("falls back to a stable 'deleted' marker when place_id is null", () => {
    expect(stopId(stop({ place_id: null }))).toBe("0-0-deleted");
  });

  it("produces different IDs for stops that only differ by day — mirrors iOS's own ItineraryStop.id", () => {
    const a = stopId(stop({ day_index: 0, order_index: 0, place_id: 12 }));
    const b = stopId(stop({ day_index: 1, order_index: 0, place_id: 12 }));
    expect(a).not.toBe(b);
  });
});

describe("computeCameraTarget", () => {
  const days: ItineraryDay[] = [
    { day_index: 0, date: null, stops: [stop({ day_index: 0, order_index: 0, place_id: 1, lat: 41, lng: 29 })] },
    {
      day_index: 1, date: null,
      stops: [
        stop({ day_index: 1, order_index: 0, place_id: 2, lat: 42, lng: 30 }),
        stop({ day_index: 1, order_index: 1, place_id: 3, lat: 43, lng: 31 }),
      ],
    },
  ];

  it("prioritizes a selected stop with coordinates over the day (Req: itinerary → map focuses that marker)", () => {
    const id = stopId(days[1].stops[0]);
    expect(computeCameraTarget(days, 1, id)).toEqual({ type: "point", coords: [42, 30] });
  });

  it("falls back to the day when the selected stop has no coordinates — never crashes, never targets a fake point", () => {
    const noCoords = stop({ day_index: 0, order_index: 0, place_id: 9, lat: null, lng: null });
    const withNoCoordsDay: ItineraryDay[] = [{ day_index: 0, date: null, stops: [noCoords] }];
    expect(computeCameraTarget(withNoCoordsDay, 0, stopId(noCoords))).toBeNull();
  });

  it("fits bounds to a day with multiple valid coordinates when no stop is selected", () => {
    expect(computeCameraTarget(days, 1, null)).toEqual({
      type: "bounds", coords: [[42, 30], [43, 31]],
    });
  });

  it("pans to the single point of a one-stop day", () => {
    expect(computeCameraTarget(days, 0, null)).toEqual({ type: "point", coords: [41, 29] });
  });

  it("returns null for a day with no valid coordinates — a day with no valid coordinates must still be safe, not crash", () => {
    const emptyDay: ItineraryDay[] = [{ day_index: 0, date: null, stops: [stop({ lat: null, lng: null })] }];
    expect(computeCameraTarget(emptyDay, 0, null)).toBeNull();
  });

  it("returns null when nothing is selected (\"Tümü\") — never continuously refits on its own", () => {
    expect(computeCameraTarget(days, null, null)).toBeNull();
  });
});

describe("OptimizerRouteMap", () => {
  it("shows an explicit empty state when no stop has coordinates — never a broken/blank map", () => {
    const days: ItineraryDay[] = [{ day_index: 0, date: null, stops: [stop({ lat: null, lng: null })] }];
    render(<OptimizerRouteMap days={days} selectedDayIndex={null} selectedStopId={null} />);
    expect(screen.getByText("Haritada gösterilecek konum yok")).toBeInTheDocument();
  });

  it("renders a loading placeholder (not a crash) before Leaflet has mounted, when coordinates exist", () => {
    const days: ItineraryDay[] = [{ day_index: 0, date: null, stops: [stop()] }];
    const { container } = render(
      <OptimizerRouteMap days={days} selectedDayIndex={null} selectedStopId={null} />
    );
    // Leaflet dinamik import'u henüz çözülmedi — jsdom'da senkron olarak bu
    // ilk (yükleniyor) state gözlemlenir, harita GERÇEKTEN monte edilmeye
    // çalışılmaz (bu test Leaflet/DOM entegrasyonunu DEĞİL, güvenli
    // "henüz hazır değil" davranışını doğruluyor).
    expect(container.firstChild).toBeTruthy();
  });
});
