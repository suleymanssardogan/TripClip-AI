import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { OptimizerResult } from "./OptimizerResult";
import * as api from "@/lib/api";
import type { Itinerary } from "@/lib/api";

// Leaflet `window`/DOM gerektirir ve bu testlerin amacı harita render'ı
// DEĞİL, OptimizerResult'ın kendi seçim/uygulama mantığı — bkz.
// OptimizerRouteMap.tsx'in kendi testinin (ayrı, aşağıda) haritayı zaten
// izole test ettiği. `stopId` GERÇEK implementasyonuyla eşleşmeli (testler
// bunu import ediyor).
vi.mock("@/components/OptimizerRouteMap", async () => {
  const actual = await vi.importActual<typeof import("@/components/OptimizerRouteMap")>(
    "@/components/OptimizerRouteMap"
  );
  return {
    __esModule: true,
    stopId: actual.stopId,
    default: ({ onSelectStop, days }: { onSelectStop?: (s: unknown) => void; days: Itinerary["days"] }) => (
      <div data-testid="fake-map">
        {days.flatMap((d) => d.stops).map((s) => (
          <button key={`${s.day_index}-${s.order_index}`} onClick={() => onSelectStop?.(s)}>
            marker-{s.name}
          </button>
        ))}
      </div>
    ),
  };
});

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, applyItinerary: vi.fn() };
});

function makeItinerary(overrides: Partial<Itinerary> = {}): Itinerary {
  return {
    id: 4, trip_id: 1, strategy_name: "greedy_distance",
    optimization_score: 87.5, total_distance_km: 12.4, total_travel_time_minutes: 29.8,
    warnings: [], created_at: "2026-08-08T10:00:00",
    days: [
      {
        day_index: 0, date: null,
        stops: [
          { place_id: 12, name: "Ayasofya", lat: 41.0086, lng: 28.9802, day_index: 0, order_index: 0,
            arrival_time: "09:00", departure_time: "09:30", visit_duration_minutes: 30,
            travel_time_to_next_minutes: 4.2, travel_distance_to_next_km: 1.75 },
          { place_id: 7, name: "Topkapı Sarayı", lat: 41.0115, lng: 28.9833, day_index: 0, order_index: 1,
            arrival_time: "09:34", departure_time: "10:34", visit_duration_minutes: 60,
            travel_time_to_next_minutes: null, travel_distance_to_next_km: null },
        ],
      },
    ],
    ...overrides,
  };
}

describe("OptimizerResult", () => {
  beforeEach(() => { vi.clearAllMocks(); });

  it("renders the optimization score", () => {
    render(<OptimizerResult itinerary={makeItinerary({ optimization_score: 87.5 })} mode="generate" />);
    expect(screen.getByText("88")).toBeInTheDocument(); // Math.round(87.5)
  });

  it("renders warnings when present", () => {
    render(<OptimizerResult itinerary={makeItinerary({ warnings: ["Açılış saatleri bilinmiyor."] })} mode="generate" />);
    expect(screen.getByText("Açılış saatleri bilinmiyor.")).toBeInTheDocument();
  });

  it("renders no warning banner when there are none", () => {
    render(<OptimizerResult itinerary={makeItinerary({ warnings: [] })} mode="generate" />);
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("day switching updates the visible stop list", () => {
    const itinerary = makeItinerary({
      days: [
        { day_index: 0, date: null, stops: [
          { place_id: 1, name: "Gün 1 Durağı", lat: 41, lng: 29, day_index: 0, order_index: 0,
            arrival_time: null, departure_time: null, visit_duration_minutes: 30,
            travel_time_to_next_minutes: null, travel_distance_to_next_km: null },
        ] },
        { day_index: 1, date: null, stops: [
          { place_id: 2, name: "Gün 2 Durağı", lat: 41, lng: 29, day_index: 1, order_index: 0,
            arrival_time: null, departure_time: null, visit_duration_minutes: 30,
            travel_time_to_next_minutes: null, travel_distance_to_next_km: null },
        ] },
      ],
    });
    render(<OptimizerResult itinerary={itinerary} mode="generate" />);
    // Çok günlü itinerary varsayılan olarak "Tümü" gösterir.
    expect(screen.getByText("Gün 1 Durağı")).toBeInTheDocument();
    expect(screen.getByText("Gün 2 Durağı")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("tab", { name: "1. Gün" }));
    expect(screen.getByText("Gün 1 Durağı")).toBeInTheDocument();
    expect(screen.queryByText("Gün 2 Durağı")).not.toBeInTheDocument();
  });

  it("selecting a map marker switches to its day and highlights the itinerary row", () => {
    const itinerary = makeItinerary({
      days: [
        { day_index: 0, date: null, stops: [
          { place_id: 1, name: "Gün 1 Durağı", lat: 41, lng: 29, day_index: 0, order_index: 0,
            arrival_time: null, departure_time: null, visit_duration_minutes: 30,
            travel_time_to_next_minutes: null, travel_distance_to_next_km: null },
        ] },
        { day_index: 1, date: null, stops: [
          { place_id: 2, name: "Gün 2 Durağı", lat: 41, lng: 29, day_index: 1, order_index: 0,
            arrival_time: null, departure_time: null, visit_duration_minutes: 30,
            travel_time_to_next_minutes: null, travel_distance_to_next_km: null },
        ] },
      ],
    });
    render(<OptimizerResult itinerary={itinerary} mode="generate" />);
    fireEvent.click(screen.getByText("marker-Gün 2 Durağı"));
    // Gün 2'ye geçilmiş olmalı — Gün 1 durağı artık görünmüyor.
    expect(screen.getByRole("tab", { name: "2. Gün" })).toHaveAttribute("aria-selected", "true");
  });

  it("clicking a stop already on the current day preserves the day selection (Req 1)", () => {
    const itinerary = makeItinerary({
      days: [
        { day_index: 0, date: null, stops: [
          { place_id: 1, name: "Gün 1 Durağı A", lat: 41, lng: 29, day_index: 0, order_index: 0,
            arrival_time: null, departure_time: null, visit_duration_minutes: 30,
            travel_time_to_next_minutes: null, travel_distance_to_next_km: null },
          { place_id: 2, name: "Gün 1 Durağı B", lat: 41, lng: 29, day_index: 0, order_index: 1,
            arrival_time: null, departure_time: null, visit_duration_minutes: 30,
            travel_time_to_next_minutes: null, travel_distance_to_next_km: null },
        ] },
      ],
    });
    render(<OptimizerResult itinerary={itinerary} mode="generate" />);
    fireEvent.click(screen.getByText("Gün 1 Durağı B"));
    expect(screen.getByText("Gün 1 Durağı B").closest('[role="button"]')).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByText("Gün 1 Durağı A")).toBeInTheDocument();
  });

  it("switching day via the day tab clears a stop selection that doesn't belong to the new day (Req 3)", () => {
    const itinerary = makeItinerary({
      days: [
        { day_index: 0, date: null, stops: [
          { place_id: 1, name: "Gün 1 Durağı", lat: 41, lng: 29, day_index: 0, order_index: 0,
            arrival_time: null, departure_time: null, visit_duration_minutes: 30,
            travel_time_to_next_minutes: null, travel_distance_to_next_km: null },
        ] },
        { day_index: 1, date: null, stops: [
          { place_id: 2, name: "Gün 2 Durağı", lat: 41, lng: 29, day_index: 1, order_index: 0,
            arrival_time: null, departure_time: null, visit_duration_minutes: 30,
            travel_time_to_next_minutes: null, travel_distance_to_next_km: null },
        ] },
      ],
    });
    render(<OptimizerResult itinerary={itinerary} mode="generate" />);
    fireEvent.click(screen.getByText("Gün 1 Durağı"));
    expect(screen.getByText("Gün 1 Durağı").closest('[role="button"]')).toHaveAttribute("aria-pressed", "true");

    fireEvent.click(screen.getByRole("tab", { name: "2. Gün" }));
    // Gün 1'in durağı artık listede bile değil, ve seçim onunla birlikte
    // temizlenmiş olmalı — kalıntı bir seçim kalmamalı.
    expect(screen.queryByText("Gün 1 Durağı")).not.toBeInTheDocument();
    expect(screen.getByText("Gün 2 Durağı").closest('[role="button"]')).toHaveAttribute("aria-pressed", "false");
  });

  it("switching day preserves a stop selection that still belongs to the new day", () => {
    const itinerary = makeItinerary({
      days: [
        { day_index: 0, date: null, stops: [
          { place_id: 1, name: "Gün 1 Durağı", lat: 41, lng: 29, day_index: 0, order_index: 0,
            arrival_time: null, departure_time: null, visit_duration_minutes: 30,
            travel_time_to_next_minutes: null, travel_distance_to_next_km: null },
        ] },
        { day_index: 1, date: null, stops: [
          { place_id: 2, name: "Gün 2 Durağı", lat: 41, lng: 29, day_index: 1, order_index: 0,
            arrival_time: null, departure_time: null, visit_duration_minutes: 30,
            travel_time_to_next_minutes: null, travel_distance_to_next_km: null },
        ] },
      ],
    });
    render(<OptimizerResult itinerary={itinerary} mode="generate" />);
    // Varsayılan "Tümü" görünümündeyken Gün 1'in durağını seç, sonra AYNI
    // güne ait sekmeye geçiş yap — seçim hâlâ o günün kapsamında olduğu
    // için KORUNMALI.
    fireEvent.click(screen.getByText("Gün 1 Durağı"));
    fireEvent.click(screen.getByRole("tab", { name: "1. Gün" }));
    expect(screen.getByText("Gün 1 Durağı").closest('[role="button"]')).toHaveAttribute("aria-pressed", "true");
  });

  it("a stop without coordinates remains selectable and never crashes", () => {
    const itinerary = makeItinerary({
      days: [{ day_index: 0, date: null, stops: [
        { place_id: 1, name: "Konumsuz Durak", lat: null, lng: null, day_index: 0, order_index: 0,
          arrival_time: null, departure_time: null, visit_duration_minutes: 30,
          travel_time_to_next_minutes: null, travel_distance_to_next_km: null },
      ] }],
    });
    render(<OptimizerResult itinerary={itinerary} mode="generate" />);
    fireEvent.click(screen.getByText("Konumsuz Durak"));
    expect(screen.getByText("Konumsuz Durak").closest('[role="button"]')).toHaveAttribute("aria-pressed", "true");
  });

  it("selection changes (stop click, day switch) never call the backend — applyItinerary is the only mutating call, and only Uygula triggers it", () => {
    const itinerary = makeItinerary({
      days: [
        { day_index: 0, date: null, stops: [
          { place_id: 1, name: "Gün 1 Durağı", lat: 41, lng: 29, day_index: 0, order_index: 0,
            arrival_time: null, departure_time: null, visit_duration_minutes: 30,
            travel_time_to_next_minutes: null, travel_distance_to_next_km: null },
        ] },
        { day_index: 1, date: null, stops: [
          { place_id: 2, name: "Gün 2 Durağı", lat: 41, lng: 29, day_index: 1, order_index: 0,
            arrival_time: null, departure_time: null, visit_duration_minutes: 30,
            travel_time_to_next_minutes: null, travel_distance_to_next_km: null },
        ] },
      ],
    });
    render(<OptimizerResult itinerary={itinerary} mode="generate" />);
    fireEvent.click(screen.getByRole("tab", { name: "1. Gün" }));
    fireEvent.click(screen.getByText("Gün 1 Durağı"));
    fireEvent.click(screen.getByRole("tab", { name: "2. Gün" }));
    expect(api.applyItinerary).not.toHaveBeenCalled();
  });

  it("the same map/list synchronization works in saved mode — selection never calls optimize or GET again", () => {
    const itinerary = makeItinerary({
      days: [
        { day_index: 0, date: null, stops: [
          { place_id: 1, name: "Gün 1 Durağı", lat: 41, lng: 29, day_index: 0, order_index: 0,
            arrival_time: null, departure_time: null, visit_duration_minutes: 30,
            travel_time_to_next_minutes: null, travel_distance_to_next_km: null },
        ] },
        { day_index: 1, date: null, stops: [
          { place_id: 2, name: "Gün 2 Durağı", lat: 41, lng: 29, day_index: 1, order_index: 0,
            arrival_time: null, departure_time: null, visit_duration_minutes: 30,
            travel_time_to_next_minutes: null, travel_distance_to_next_km: null },
        ] },
      ],
    });
    render(<OptimizerResult itinerary={itinerary} mode="saved" />);
    fireEvent.click(screen.getByText("marker-Gün 2 Durağı"));
    expect(screen.getByRole("tab", { name: "2. Gün" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByText("Gün 2 Durağı").closest('[role="button"]')).toHaveAttribute("aria-pressed", "true");
  });

  it("selects a stop via the keyboard (Enter/Space), not just click — accessibility-critical interaction", () => {
    render(<OptimizerResult itinerary={makeItinerary()} mode="generate" />);
    const row = screen.getByText("Topkapı Sarayı").closest('[role="button"]') as HTMLElement;
    expect(row).toHaveAttribute("aria-pressed", "false");

    fireEvent.keyDown(row, { key: "Enter" });
    expect(row).toHaveAttribute("aria-pressed", "true");
  });

  it("indicates a stop with missing coordinates", () => {
    const itinerary = makeItinerary({
      days: [{ day_index: 0, date: null, stops: [
        { place_id: 1, name: "Konumsuz Durak", lat: null, lng: null, day_index: 0, order_index: 0,
          arrival_time: null, departure_time: null, visit_duration_minutes: 30,
          travel_time_to_next_minutes: null, travel_distance_to_next_km: null },
      ] }],
    });
    render(<OptimizerResult itinerary={itinerary} mode="generate" />);
    expect(screen.getByText("konum yok")).toBeInTheDocument();
  });

  it("shows a confirmation dialog before applying", () => {
    render(<OptimizerResult itinerary={makeItinerary()} mode="generate" />);
    fireEvent.click(screen.getByText("Trip'e Uygula"));
    expect(screen.getByText("Bu itinerary Trip'e uygulansın mı?")).toBeInTheDocument();
  });

  it("applies successfully and calls onApplied", async () => {
    vi.mocked(api.applyItinerary).mockResolvedValue({
      trip_id: 1, itinerary_id: 4, stops: [], stops_count: 0, applied_at: "2026-08-08T10:05:00",
    });
    const onApplied = vi.fn();
    render(<OptimizerResult itinerary={makeItinerary()} mode="generate" onApplied={onApplied} />);
    fireEvent.click(screen.getByText("Trip'e Uygula"));
    fireEvent.click(screen.getByRole("button", { name: "Uygula" }));

    await waitFor(() => expect(onApplied).toHaveBeenCalled());
    expect(api.applyItinerary).toHaveBeenCalledWith(4);
    expect(screen.getByText("Gezinin durak listesi güncellendi.")).toBeInTheDocument();
  });

  it("shows an error and keeps the itinerary view on apply failure", async () => {
    vi.mocked(api.applyItinerary).mockRejectedValue(new Error("Bu geziyi düzenleme yetkin yok."));
    render(<OptimizerResult itinerary={makeItinerary()} mode="generate" />);
    fireEvent.click(screen.getByText("Trip'e Uygula"));
    fireEvent.click(screen.getByRole("button", { name: "Uygula" }));

    await waitFor(() => expect(screen.getByText("Bu geziyi düzenleme yetkin yok.")).toBeInTheDocument());
    // İtinerary görünümü hâlâ orada — kayıp değil.
    expect(screen.getByText("Ayasofya")).toBeInTheDocument();
  });

  it("prevents re-entrant apply submissions while one is in flight", async () => {
    let resolveApply: (v: api.ApplyResult) => void = () => {};
    vi.mocked(api.applyItinerary).mockReturnValue(
      new Promise((resolve) => { resolveApply = resolve; })
    );
    render(<OptimizerResult itinerary={makeItinerary()} mode="generate" />);
    fireEvent.click(screen.getByText("Trip'e Uygula"));
    fireEvent.click(screen.getByRole("button", { name: "Uygula" }));

    expect(screen.getByRole("button", { name: /İşleniyor/ })).toBeDisabled();

    resolveApply({ trip_id: 1, itinerary_id: 4, stops: [], stops_count: 0, applied_at: "x" });
    await waitFor(() => expect(api.applyItinerary).toHaveBeenCalledTimes(1));
  });

  it("shows a 'Kayıtlı İtinerary' badge in saved mode", () => {
    render(<OptimizerResult itinerary={makeItinerary()} mode="saved" />);
    expect(screen.getByText("Kayıtlı İtinerary")).toBeInTheDocument();
  });
});
