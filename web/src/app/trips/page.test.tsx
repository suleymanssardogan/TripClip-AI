import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import TripsPage from "./page";
import * as api from "@/lib/api";

const push = vi.fn();
// `router` sabit referans olmalı — üstteki tarih notu diğer sayfa
// testlerindeki aynı gerekçe: aksi halde her render'da useEffect yeniden
// tetiklenir ve gereksiz yeniden-fetch'ler yerel state ile yarışır.
const router = { push };
vi.mock("next/navigation", () => ({
  useRouter: () => router,
  usePathname: () => "/trips",
}));

vi.mock("@/components/Navbar", () => ({ default: () => null }));

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, getSession: vi.fn(), getTrips: vi.fn() };
});

function trip(overrides: Partial<api.TripSummary> = {}): api.TripSummary {
  return {
    id: 1, title: "İstanbul Gezisi", total_distance_km: 12.4,
    created_at: "2026-08-08T10:00:00", stops_count: 5, role: "owner",
    ...overrides,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(api.getSession).mockResolvedValue({ user_id: 1, email: "test@example.com" });
});

describe("TripsPage", () => {
  it("renders each trip returned by the server", async () => {
    vi.mocked(api.getTrips).mockResolvedValue({
      trips: [trip({ id: 1, title: "İstanbul Gezisi" }), trip({ id: 2, title: "Kapadokya Gezisi" })],
    });
    render(<TripsPage />);
    await waitFor(() => expect(screen.getByText("İstanbul Gezisi")).toBeInTheDocument());
    expect(screen.getByText("Kapadokya Gezisi")).toBeInTheDocument();
  });

  it("shows an empty state pointing users to the iOS app when there are no trips", async () => {
    vi.mocked(api.getTrips).mockResolvedValue({ trips: [] });
    render(<TripsPage />);
    await waitFor(() => expect(screen.getByText("Henüz gezi yok")).toBeInTheDocument());
  });

  it("navigates to the trip detail page on click", async () => {
    vi.mocked(api.getTrips).mockResolvedValue({ trips: [trip({ id: 7 })] });
    render(<TripsPage />);
    await waitFor(() => expect(screen.getByRole("link")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("link"));
    expect(push).toHaveBeenCalledWith("/trips/7");
  });

  it("shows an error state with retry when the trip list fails to load", async () => {
    vi.mocked(api.getTrips).mockRejectedValue(new Error("network down"));
    render(<TripsPage />);
    await waitFor(() => expect(screen.getByText("Geziler yüklenemedi")).toBeInTheDocument());
    expect(screen.getByText("Tekrar Dene")).toBeInTheDocument();
  });
  it("keeps loaded trips after a failed page and retries the same offset", async () => {
    vi.mocked(api.getTrips)
      .mockResolvedValueOnce({ trips: [trip({ id: 1 })], total: 2, has_more: true })
      .mockRejectedValueOnce(new Error("page unavailable"))
      .mockResolvedValueOnce({ trips: [trip({ id: 2, title: "İkinci Gezi" })], total: 2, has_more: false });
    render(<TripsPage />);
    fireEvent.click(await screen.findByRole("button", { name: "Daha fazla yükle" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Yükleme başarısız");
    expect(screen.getByText("İstanbul Gezisi")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Daha fazla yükle" }));
    expect(await screen.findByText("İkinci Gezi")).toBeInTheDocument();
    expect(api.getTrips).toHaveBeenNthCalledWith(2, 20, 1);
    expect(api.getTrips).toHaveBeenNthCalledWith(3, 20, 1);
    expect(screen.queryByRole("button", { name: "Daha fazla yükle" })).not.toBeInTheDocument();
  });

});
