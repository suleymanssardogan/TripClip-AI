import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import ItineraryHistoryPage from "./page";
import * as api from "@/lib/api";

const push = vi.fn();
// `router` must be referentially stable across renders — the page's
// useEffect depends on it, and a fresh object literal per call would
// re-fire the effect (and re-fetch) on every render, racing local updates.
const router = { push };
vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "1" }),
  useRouter: () => router,
  usePathname: () => "/trips/1/history",
}));

// Navbar itself renders ThemeToggle, which requires a <ThemeProvider> that
// this page-level test doesn't set up — Navbar isn't what's under test here.
vi.mock("@/components/Navbar", () => ({ default: () => null }));

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, getItineraries: vi.fn(), deleteItinerary: vi.fn() };
});

function summary(overrides: Partial<api.ItinerarySummary> = {}): api.ItinerarySummary {
  return {
    id: 1, trip_id: 1, strategy_name: "greedy_distance", optimization_score: 87.5,
    total_distance_km: 12.4, total_travel_time_minutes: 29.8, warnings: [],
    created_at: "2026-08-08T10:00:00", days_count: 1, stops_count: 2,
    ...overrides,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.setItem("token", "test-token");
});

describe("ItineraryHistoryPage", () => {
  it("renders itineraries in the order the server returns (newest-first is a server contract)", async () => {
    vi.mocked(api.getItineraries).mockResolvedValue({
      itineraries: [summary({ id: 2, optimization_score: 90 }), summary({ id: 1, optimization_score: 70 })],
    });
    render(<ItineraryHistoryPage />);
    await waitFor(() => expect(screen.getAllByText(/90|70/).length).toBeGreaterThan(0));
    const scores = screen.getAllByText(/^(90|70)$/).map((el) => el.textContent);
    expect(scores).toEqual(["90", "70"]);
  });

  it("links each row to the GET-only saved-itinerary view (?itineraryId=), never re-triggering optimize", async () => {
    vi.mocked(api.getItineraries).mockResolvedValue({ itineraries: [summary({ id: 42 })] });
    render(<ItineraryHistoryPage />);
    await waitFor(() => expect(screen.getByRole("link")).toBeInTheDocument());
    expect(screen.getByRole("link")).toHaveAttribute("href", "/trips/1/optimize?itineraryId=42");
  });

  it("shows an empty state when there is no history", async () => {
    vi.mocked(api.getItineraries).mockResolvedValue({ itineraries: [] });
    render(<ItineraryHistoryPage />);
    await waitFor(() => expect(screen.getByText("Henüz optimizasyon geçmişi yok")).toBeInTheDocument());
  });

  it("requires confirmation before deleting, then removes only that row locally", async () => {
    vi.mocked(api.getItineraries).mockResolvedValue({
      itineraries: [summary({ id: 1 }), summary({ id: 2 })],
    });
    vi.mocked(api.deleteItinerary).mockResolvedValue({ success: true });
    render(<ItineraryHistoryPage />);
    await waitFor(() => expect(screen.getAllByLabelText("İtinerary'i sil")).toHaveLength(2));

    fireEvent.click(screen.getAllByLabelText("İtinerary'i sil")[0]);
    expect(screen.getByText("Bu optimizasyon geçmişini silmek istediğine emin misin?")).toBeInTheDocument();
    expect(api.deleteItinerary).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "Sil" }));
    await waitFor(() => expect(api.deleteItinerary).toHaveBeenCalledWith(1));
    await waitFor(() => expect(screen.getAllByLabelText("İtinerary'i sil")).toHaveLength(1));
  });

  it("prevents a re-entrant delete submission while one is already in flight", async () => {
    vi.mocked(api.getItineraries).mockResolvedValue({ itineraries: [summary({ id: 1 })] });
    let resolveDelete: (v: { success: boolean }) => void = () => {};
    vi.mocked(api.deleteItinerary).mockReturnValue(new Promise((resolve) => { resolveDelete = resolve; }));
    render(<ItineraryHistoryPage />);
    await waitFor(() => expect(screen.getByLabelText("İtinerary'i sil")).toBeInTheDocument());

    fireEvent.click(screen.getByLabelText("İtinerary'i sil"));
    fireEvent.click(screen.getByRole("button", { name: "Sil" }));
    expect(screen.getByRole("button", { name: /İşleniyor/ })).toBeDisabled();

    resolveDelete({ success: true });
    await waitFor(() => expect(screen.queryByLabelText("İtinerary'i sil")).not.toBeInTheDocument());
    expect(api.deleteItinerary).toHaveBeenCalledTimes(1);
  });

  it("keeps the row visible and shows an error toast when deletion fails", async () => {
    vi.mocked(api.getItineraries).mockResolvedValue({ itineraries: [summary({ id: 1 })] });
    vi.mocked(api.deleteItinerary).mockRejectedValue(new Error("Bu itinerary artık mevcut değil."));
    render(<ItineraryHistoryPage />);
    await waitFor(() => expect(screen.getByLabelText("İtinerary'i sil")).toBeInTheDocument());

    fireEvent.click(screen.getByLabelText("İtinerary'i sil"));
    fireEvent.click(screen.getByRole("button", { name: "Sil" }));

    await waitFor(() => expect(screen.getByText("Bu itinerary artık mevcut değil.")).toBeInTheDocument());
    expect(screen.getByLabelText("İtinerary'i sil")).toBeInTheDocument();
  });
});
