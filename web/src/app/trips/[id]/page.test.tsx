import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import TripDetailPage from "./page";
import * as api from "@/lib/api";

const push = vi.fn();
const router = { push };
vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "1" }),
  useRouter: () => router,
  usePathname: () => "/trips/1",
}));

vi.mock("@/components/Navbar", () => ({ default: () => null }));

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
});
