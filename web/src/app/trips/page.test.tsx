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
  return { ...actual, getTrips: vi.fn() };
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
  localStorage.setItem("token", "test-token");
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
});
