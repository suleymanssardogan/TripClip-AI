import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import OptimizePage from "./page";
import * as api from "@/lib/api";
import type { TripDetail, Itinerary, OptimizeTripRequest } from "@/lib/api";

const push = vi.fn();
const router = { push };
// `itineraryIdParam` bu modülün dışından, her testin başında ayarlanır —
// `?itineraryId=` sorgu parametresinin varlığı/yokluğu saved-mode'u
// tetikleyen tek koşuldur (bkz. sayfanın kendi doc yorumu).
let itineraryIdParam: string | null = null;
vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "1" }),
  useRouter: () => router,
  usePathname: () => "/trips/1/optimize",
  useSearchParams: () => ({ get: (key: string) => (key === "itineraryId" ? itineraryIdParam : null) }),
}));

vi.mock("@/components/Navbar", () => ({ default: () => null }));

// Bu sayfa testinin amacı sayfanın KENDİ orkestrasyon mantığı (yükleme,
// generate re-entrancy koruması, saved-mode GET-only davranışı) — form/sonuç
// bileşenlerinin kendi iç render mantığı zaten OptimizerConfigForm.test.tsx
// ve OptimizerResult.test.tsx'te ayrı test ediliyor.
vi.mock("@/components/optimizer/OptimizerConfigForm", () => ({
  OptimizerConfigForm: ({
    onSubmit, submitting,
  }: {
    onSubmit: (c: OptimizeTripRequest) => void;
    submitting: boolean;
  }) => (
    <button disabled={submitting} onClick={() => onSubmit({ selected_place_ids: [1, 2] })}>
      fake-optimize-submit
    </button>
  ),
}));

vi.mock("@/components/optimizer/OptimizerResult", () => ({
  OptimizerResult: ({ itinerary, mode }: { itinerary: Itinerary; mode: string }) => (
    <div data-testid="fake-result">
      sonuç-{itinerary.id}-{mode}
    </div>
  ),
}));

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, getTrip: vi.fn(), getItinerary: vi.fn(), optimizeTrip: vi.fn() };
});

function tripDetail(overrides: Partial<TripDetail> = {}): TripDetail {
  return {
    id: 1, title: "İstanbul Gezisi", total_distance_km: 12.4, created_at: "2026-08-08T10:00:00",
    days: [[
      { place_id: 1, name: "Ayasofya", lat: 41, lng: 29, city: "İstanbul", category: "tarihi", day_index: 0, order_index: 0 },
    ]],
    stops_count: 1, owner_id: 1, your_role: "owner",
    applied_itinerary_id: null, itinerary_applied_at: null,
    ...overrides,
  };
}

function itinerary(overrides: Partial<Itinerary> = {}): Itinerary {
  return {
    id: 9, trip_id: 1, strategy_name: "greedy_distance", optimization_score: 90,
    total_distance_km: 5, total_travel_time_minutes: 20, warnings: [],
    created_at: "2026-08-08T10:00:00", days: [],
    ...overrides,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.setItem("token", "test-token");
  itineraryIdParam = null;
});

describe("OptimizePage", () => {
  it("generate mode: shows the config form when no itinerary exists yet", async () => {
    vi.mocked(api.getTrip).mockResolvedValue(tripDetail());
    render(<OptimizePage />);
    await waitFor(() => expect(screen.getByText("fake-optimize-submit")).toBeInTheDocument());
    expect(api.getItinerary).not.toHaveBeenCalled();
  });

  it("generate mode: submitting the form calls optimizeTrip with the exact config and renders the result", async () => {
    vi.mocked(api.getTrip).mockResolvedValue(tripDetail());
    vi.mocked(api.optimizeTrip).mockResolvedValue(itinerary({ id: 9 }));
    render(<OptimizePage />);
    await waitFor(() => expect(screen.getByText("fake-optimize-submit")).toBeInTheDocument());

    fireEvent.click(screen.getByText("fake-optimize-submit"));
    await waitFor(() => expect(screen.getByTestId("fake-result")).toBeInTheDocument());
    expect(api.optimizeTrip).toHaveBeenCalledWith(1, { selected_place_ids: [1, 2] });
    expect(screen.getByText("sonuç-9-generate")).toBeInTheDocument();
  });

  it("generate mode: prevents a duplicate submission while one is already in flight", async () => {
    vi.mocked(api.getTrip).mockResolvedValue(tripDetail());
    let resolveOptimize: (v: Itinerary) => void = () => {};
    vi.mocked(api.optimizeTrip).mockReturnValue(new Promise((resolve) => { resolveOptimize = resolve; }));
    render(<OptimizePage />);
    await waitFor(() => expect(screen.getByText("fake-optimize-submit")).toBeInTheDocument());

    fireEvent.click(screen.getByText("fake-optimize-submit"));
    fireEvent.click(screen.getByText("fake-optimize-submit"));
    fireEvent.click(screen.getByText("fake-optimize-submit"));
    expect(screen.getByText("fake-optimize-submit")).toBeDisabled();

    resolveOptimize(itinerary());
    await waitFor(() => expect(screen.getByTestId("fake-result")).toBeInTheDocument());
    expect(api.optimizeTrip).toHaveBeenCalledTimes(1);
  });

  it("generate mode: shows an error and keeps the form visible when optimize fails", async () => {
    vi.mocked(api.getTrip).mockResolvedValue(tripDetail());
    vi.mocked(api.optimizeTrip).mockRejectedValue(new Error("Optimizasyon başarısız oldu."));
    render(<OptimizePage />);
    await waitFor(() => expect(screen.getByText("fake-optimize-submit")).toBeInTheDocument());

    fireEvent.click(screen.getByText("fake-optimize-submit"));
    await waitFor(() => expect(screen.getByText("Optimizasyon başarısız oldu.")).toBeInTheDocument());
    expect(screen.getByText("fake-optimize-submit")).toBeInTheDocument();
    expect(screen.queryByTestId("fake-result")).not.toBeInTheDocument();
  });

  it("saved mode (?itineraryId=): loads via GET only, never calls optimizeTrip", async () => {
    itineraryIdParam = "9";
    vi.mocked(api.getTrip).mockResolvedValue(tripDetail());
    vi.mocked(api.getItinerary).mockResolvedValue(itinerary({ id: 9 }));
    render(<OptimizePage />);
    await waitFor(() => expect(screen.getByTestId("fake-result")).toBeInTheDocument());
    expect(api.getItinerary).toHaveBeenCalledWith(9);
    expect(api.optimizeTrip).not.toHaveBeenCalled();
    expect(screen.getByText("sonuç-9-saved")).toBeInTheDocument();
  });

  it("saved mode: an invalid/deleted itinerary ID shows an error with retry, not a crash", async () => {
    itineraryIdParam = "999";
    vi.mocked(api.getTrip).mockResolvedValue(tripDetail());
    vi.mocked(api.getItinerary).mockRejectedValue(new Error("Bu itinerary artık mevcut değil."));
    render(<OptimizePage />);
    await waitFor(() => expect(screen.getByText("Bu itinerary artık mevcut değil.")).toBeInTheDocument());
    expect(screen.getByText("Tekrar Dene")).toBeInTheDocument();
    expect(screen.queryByTestId("fake-result")).not.toBeInTheDocument();
  });

  it("unmounting while the initial load is still in flight does not throw", async () => {
    let resolveTrip: (v: TripDetail) => void = () => {};
    vi.mocked(api.getTrip).mockReturnValue(new Promise((resolve) => { resolveTrip = resolve; }));
    const { unmount } = render(<OptimizePage />);
    // Yükleme hâlâ sürerken (promise henüz çözülmeden) sayfadan ayrıl —
    // beklemedeki `.then()` unmount SONRASI çalışacak (bkz. Req 6 "navigating
    // away during loading does not leave stale state behind").
    unmount();
    expect(() => resolveTrip(tripDetail())).not.toThrow();
    await new Promise((r) => setTimeout(r, 0));
  });
});
