import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import TripDetailPage from "./page";
import * as api from "@/lib/api";
import type { ItineraryDay, ItineraryStop } from "@/lib/api";

const push = vi.fn();
const router = { push };
let searchParamsMap = new Map<string, string>();
vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "1" }),
  useRouter: () => router,
  usePathname: () => "/trips/1",
  useSearchParams: () => ({ get: (key: string) => searchParamsMap.get(key) ?? null }),
}));

vi.mock("@/components/Navbar", () => ({ default: () => null }));

// Bu sayfa testinin amacı sayfanın KENDİ gün/durak seçim mantığı — haritanın
// gerçek Leaflet render'ı `OptimizerRouteMap.test.tsx`'te ayrı test ediliyor
// (`OptimizerResult.test.tsx`'teki AYNI mock deseni: gerçek `stopId`, sahte
// marker-buton listesi).
vi.mock("@/components/OptimizerRouteMap", async () => {
  const actual = await vi.importActual<typeof import("@/components/OptimizerRouteMap")>(
    "@/components/OptimizerRouteMap"
  );
  return {
    __esModule: true,
    stopId: actual.stopId,
    default: ({ onSelectStop, days }: { onSelectStop?: (s: ItineraryStop) => void; days: ItineraryDay[] }) => (
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
  return { ...actual, getTrip: vi.fn() };
});

function trip(overrides: Partial<api.TripDetail> = {}): api.TripDetail {
  return {
    id: 1, title: "İstanbul Gezisi", total_distance_km: 12.4,
    created_at: "2026-08-08T10:00:00",
    days: [[
      { place_id: 1, name: "Ayasofya", lat: 41, lng: 29, city: "İstanbul", category: "tarihi", day_index: 0, order_index: 0 },
    ]],
    stops_count: 1, owner_id: 1, your_role: "owner",
    applied_itinerary_id: null, itinerary_applied_at: null,
    ...overrides,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.setItem("token", "test-token");
  searchParamsMap = new Map();
});

describe("TripDetailPage", () => {
  it("renders the trip title and stops", async () => {
    vi.mocked(api.getTrip).mockResolvedValue(trip());
    render(<TripDetailPage />);
    await waitFor(() => expect(screen.getByText("İstanbul Gezisi")).toBeInTheDocument());
    expect(screen.getByText("Ayasofya")).toBeInTheDocument();
  });

  it("shows the Optimize Et entry point for an owner", async () => {
    vi.mocked(api.getTrip).mockResolvedValue(trip({ your_role: "owner" }));
    render(<TripDetailPage />);
    await waitFor(() => expect(screen.getByText("Optimize Et")).toBeInTheDocument());
  });

  it("shows the Optimize Et entry point for an editor", async () => {
    vi.mocked(api.getTrip).mockResolvedValue(trip({ your_role: "editor" }));
    render(<TripDetailPage />);
    await waitFor(() => expect(screen.getByText("Optimize Et")).toBeInTheDocument());
  });

  it("hides the Optimize Et entry point for a read-only viewer", async () => {
    vi.mocked(api.getTrip).mockResolvedValue(trip({ your_role: "viewer" }));
    render(<TripDetailPage />);
    await waitFor(() => expect(screen.getByText("İstanbul Gezisi")).toBeInTheDocument());
    expect(screen.queryByText("Optimize Et")).not.toBeInTheDocument();
  });

  it("always shows history and apply-history entry points, regardless of role", async () => {
    vi.mocked(api.getTrip).mockResolvedValue(trip({ your_role: "viewer" }));
    render(<TripDetailPage />);
    await waitFor(() => expect(screen.getByText("Optimizasyon Geçmişi")).toBeInTheDocument());
    expect(screen.getByText("Uygulama Geçmişi")).toBeInTheDocument();
  });

  it("shows an error state with retry when the trip fails to load", async () => {
    vi.mocked(api.getTrip).mockRejectedValue(new Error("Bu geziye erişimin yok."));
    render(<TripDetailPage />);
    await waitFor(() => expect(screen.getByText("Bu geziye erişimin yok.")).toBeInTheDocument());
    expect(screen.getByText("Tekrar Dene")).toBeInTheDocument();
  });

  function multiDayTrip(): api.TripDetail {
    return trip({
      stops_count: 2,
      days: [
        [{ place_id: 1, name: "Gün 1 Durağı", lat: 41, lng: 29, city: null, category: null, day_index: 0, order_index: 0 }],
        [{ place_id: 2, name: "Gün 2 Durağı", lat: 42, lng: 30, city: null, category: null, day_index: 1, order_index: 0 }],
      ],
    });
  }

  it("shows day-jump chips for a multi-day trip, and none for a single-day trip", async () => {
    vi.mocked(api.getTrip).mockResolvedValue(multiDayTrip());
    render(<TripDetailPage />);
    await waitFor(() => expect(screen.getByText("Gün 1 Durağı")).toBeInTheDocument());
    expect(screen.getByRole("tablist")).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "1. Gün" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "2. Gün" })).toBeInTheDocument();
  });

  it("does not show day-jump chips for a single-day trip", async () => {
    vi.mocked(api.getTrip).mockResolvedValue(trip());
    render(<TripDetailPage />);
    await waitFor(() => expect(screen.getByText("Ayasofya")).toBeInTheDocument());
    expect(screen.queryByRole("tablist")).not.toBeInTheDocument();
  });

  it("switching day via the day tab filters the visible stop list", async () => {
    vi.mocked(api.getTrip).mockResolvedValue(multiDayTrip());
    render(<TripDetailPage />);
    await waitFor(() => expect(screen.getByText("Gün 1 Durağı")).toBeInTheDocument());
    expect(screen.getByText("Gün 2 Durağı")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("tab", { name: "1. Gün" }));
    expect(screen.getByText("Gün 1 Durağı")).toBeInTheDocument();
    expect(screen.queryByText("Gün 2 Durağı")).not.toBeInTheDocument();
  });

  it("selecting a map marker switches to its day and highlights the itinerary row", async () => {
    vi.mocked(api.getTrip).mockResolvedValue(multiDayTrip());
    render(<TripDetailPage />);
    await waitFor(() => expect(screen.getByText("marker-Gün 2 Durağı")).toBeInTheDocument());

    fireEvent.click(screen.getByText("marker-Gün 2 Durağı"));
    expect(screen.getByRole("tab", { name: "2. Gün" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByText("Gün 2 Durağı").closest('[role="button"]')).toHaveAttribute("aria-pressed", "true");
  });

  it("selects a stop via the keyboard (Enter/Space), not just click", async () => {
    vi.mocked(api.getTrip).mockResolvedValue(trip());
    render(<TripDetailPage />);
    await waitFor(() => expect(screen.getByText("Ayasofya")).toBeInTheDocument());
    const row = screen.getByText("Ayasofya").closest('[role="button"]') as HTMLElement;
    expect(row).toHaveAttribute("aria-pressed", "false");
    fireEvent.keyDown(row, { key: "Enter" });
    expect(row).toHaveAttribute("aria-pressed", "true");
  });

  it("switching day via the tab clears a stop selection that doesn't belong to the new day", async () => {
    vi.mocked(api.getTrip).mockResolvedValue(multiDayTrip());
    render(<TripDetailPage />);
    await waitFor(() => expect(screen.getByText("Gün 1 Durağı")).toBeInTheDocument());

    fireEvent.click(screen.getByText("Gün 1 Durağı"));
    expect(screen.getByText("Gün 1 Durağı").closest('[role="button"]')).toHaveAttribute("aria-pressed", "true");

    fireEvent.click(screen.getByRole("tab", { name: "2. Gün" }));
    expect(screen.queryByText("Gün 1 Durağı")).not.toBeInTheDocument();
    expect(screen.getByText("Gün 2 Durağı").closest('[role="button"]')).toHaveAttribute("aria-pressed", "false");
  });

  it("shows an applied-itinerary indicator linking to Apply History when the trip has an applied itinerary", async () => {
    vi.mocked(api.getTrip).mockResolvedValue(trip({
      applied_itinerary_id: 4, itinerary_applied_at: "2026-08-08T10:05:00",
    }));
    render(<TripDetailPage />);
    await waitFor(() => expect(screen.getByText("Bir optimizer itinerary'si uygulandı")).toBeInTheDocument());
    const links = screen.getAllByRole("link").filter((a) => a.getAttribute("href") === "/trips/1/apply-history");
    expect(links.length).toBeGreaterThan(0);
  });

  it("shows no applied-itinerary indicator when the trip has never had one applied", async () => {
    vi.mocked(api.getTrip).mockResolvedValue(trip({ applied_itinerary_id: null }));
    render(<TripDetailPage />);
    await waitFor(() => expect(screen.getByText("Ayasofya")).toBeInTheDocument());
    expect(screen.queryByText("Bir optimizer itinerary'si uygulandı")).not.toBeInTheDocument();
  });

  it("renders the map only when the trip has stops", async () => {
    vi.mocked(api.getTrip).mockResolvedValue(trip({ stops_count: 0, days: [] }));
    render(<TripDetailPage />);
    await waitFor(() => expect(screen.getByText("Bu gezide henüz durak yok.")).toBeInTheDocument());
    expect(screen.queryByTestId("fake-map")).not.toBeInTheDocument();
  });

  it("links to the AI Assistant entry point", async () => {
    vi.mocked(api.getTrip).mockResolvedValue(trip());
    render(<TripDetailPage />);
    await waitFor(() => expect(screen.getByText("AI Asistan")).toBeInTheDocument());
    expect(screen.getByText("AI Asistan").closest("a")).toHaveAttribute("href", "/trips/1/assistant");
  });

  it("resolves ?focusDay=&focusPlace= (from an assistant reference) to a real selection once the trip loads", async () => {
    searchParamsMap.set("focusDay", "0");
    searchParamsMap.set("focusPlace", "1");
    vi.mocked(api.getTrip).mockResolvedValue(trip());
    render(<TripDetailPage />);
    await waitFor(() =>
      expect(screen.getByText("Ayasofya").closest('[role="button"]')).toHaveAttribute("aria-pressed", "true")
    );
  });

  it("ignores a focus reference to a stop that doesn't exist, without crashing", async () => {
    searchParamsMap.set("focusDay", "5");
    searchParamsMap.set("focusPlace", "999");
    vi.mocked(api.getTrip).mockResolvedValue(trip());
    render(<TripDetailPage />);
    await waitFor(() => expect(screen.getByText("Ayasofya")).toBeInTheDocument());
    expect(screen.getByText("Ayasofya").closest('[role="button"]')).toHaveAttribute("aria-pressed", "false");
  });
});
