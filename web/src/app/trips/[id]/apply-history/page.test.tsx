import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor, within } from "@testing-library/react";
import ApplyHistoryPage from "./page";
import * as api from "@/lib/api";
import { ApiError } from "@/lib/api";

const push = vi.fn();
// `router` must be referentially stable across renders — the page's
// useEffect depends on it, and a fresh object literal per call would
// re-fire the effect (and re-fetch) on every render, racing local updates.
const router = { push };
vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "1" }),
  useRouter: () => router,
  usePathname: () => "/trips/1/apply-history",
}));

// Navbar itself renders ThemeToggle, which requires a <ThemeProvider> that
// this page-level test doesn't set up — Navbar isn't what's under test here.
vi.mock("@/components/Navbar", () => ({ default: () => null }));

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, getApplyHistory: vi.fn(), undoApply: vi.fn() };
});

function entry(overrides: Partial<api.ApplyHistoryEntry> = {}): api.ApplyHistoryEntry {
  return {
    id: 1, itinerary_id: 4, itinerary_created_at: "2026-08-08T10:00:00",
    is_undo: false, applied_at: "2026-08-08T10:05:00", actor_user_id: 1,
    is_undoable: false,
    ...overrides,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.setItem("token", "test-token");
});

describe("ApplyHistoryPage", () => {
  it("renders entries in the order the server returns (newest-first is a server contract)", async () => {
    vi.mocked(api.getApplyHistory).mockResolvedValue({
      entries: [entry({ id: 2, applied_at: "2026-08-08T12:00:00" }), entry({ id: 1, applied_at: "2026-08-08T10:00:00" })],
    });
    render(<ApplyHistoryPage />);
    await waitFor(() => expect(screen.getAllByText("Itinerary uygulandı").length).toBe(2));
    const rows = screen.getAllByText("Itinerary uygulandı");
    // İlk satır en yeni applied_at değerine ait olmalı (server sırası korunur).
    expect(rows[0].closest("div.p-4")).toHaveTextContent(new Date("2026-08-08T12:00:00").toLocaleString("tr-TR"));
  });

  it("shows Geri Al only for the latest (server-flagged is_undoable) entry", async () => {
    vi.mocked(api.getApplyHistory).mockResolvedValue({
      entries: [entry({ id: 2, is_undoable: true }), entry({ id: 1, is_undoable: false })],
    });
    render(<ApplyHistoryPage />);
    await waitFor(() => expect(screen.getAllByText("Itinerary uygulandı").length).toBe(2));
    expect(screen.getAllByText("Geri Al")).toHaveLength(1);
  });

  it("shows an empty state when there is no apply history", async () => {
    vi.mocked(api.getApplyHistory).mockResolvedValue({ entries: [] });
    render(<ApplyHistoryPage />);
    await waitFor(() => expect(screen.getByText("Henüz uygulama geçmişi yok")).toBeInTheDocument());
  });

  it("undoes successfully, shows a success banner, and refreshes from the server", async () => {
    vi.mocked(api.getApplyHistory)
      .mockResolvedValueOnce({ entries: [entry({ id: 2, is_undoable: true })] })
      .mockResolvedValueOnce({ entries: [entry({ id: 3, is_undo: true, is_undoable: false })] });
    vi.mocked(api.undoApply).mockResolvedValue({
      trip_id: 1, history_id: 2, itinerary_id: null, stops: [], stops_count: 0, applied_at: "x",
    });
    render(<ApplyHistoryPage />);
    await waitFor(() => expect(screen.getByText("Geri Al")).toBeInTheDocument());

    fireEvent.click(screen.getByText("Geri Al"));
    expect(screen.getByText("Son optimizasyon uygulamasını geri almak istediğine emin misin?")).toBeInTheDocument();

    fireEvent.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Geri Al" }));
    await waitFor(() => expect(api.undoApply).toHaveBeenCalledWith(1, 2));
    await waitFor(() => expect(screen.getByText("Geri alma işlemi tamamlandı.")).toBeInTheDocument());
    // Yerel tahmin değil, sunucudan yeniden yükleme — ikinci mock cevabı görünmeli.
    await waitFor(() => expect(api.getApplyHistory).toHaveBeenCalledTimes(2));
  });

  it("on STALE_UNDO (409), shows a clear message and refreshes history instead of a local mutation", async () => {
    vi.mocked(api.getApplyHistory)
      .mockResolvedValueOnce({ entries: [entry({ id: 2, is_undoable: true })] })
      .mockResolvedValueOnce({ entries: [entry({ id: 5, is_undo: true, is_undoable: true })] });
    vi.mocked(api.undoApply).mockRejectedValue(new ApiError("stale", 409, "STALE_UNDO"));
    render(<ApplyHistoryPage />);
    await waitFor(() => expect(screen.getByText("Geri Al")).toBeInTheDocument());

    fireEvent.click(screen.getByText("Geri Al"));
    fireEvent.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Geri Al" }));

    await waitFor(() =>
      expect(
        screen.getByText("Bu kayıt artık en son değil — başka bir işlem araya girdi. Liste güncellendi.")
      ).toBeInTheDocument()
    );
    await waitFor(() => expect(api.getApplyHistory).toHaveBeenCalledTimes(2));
  });

  it("prevents a re-entrant undo submission while one is already in flight", async () => {
    vi.mocked(api.getApplyHistory).mockResolvedValue({ entries: [entry({ id: 2, is_undoable: true })] });
    let resolveUndo: (v: api.UndoResult) => void = () => {};
    vi.mocked(api.undoApply).mockReturnValue(new Promise((resolve) => { resolveUndo = resolve; }));
    render(<ApplyHistoryPage />);
    await waitFor(() => expect(screen.getByText("Geri Al")).toBeInTheDocument());

    fireEvent.click(screen.getByText("Geri Al"));
    fireEvent.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Geri Al" }));
    expect(within(screen.getByRole("alertdialog")).getByRole("button", { name: /İşleniyor/ })).toBeDisabled();

    resolveUndo({ trip_id: 1, history_id: 2, itinerary_id: null, stops: [], stops_count: 0, applied_at: "x" });
    await waitFor(() => expect(screen.getByText("Geri alma işlemi tamamlandı.")).toBeInTheDocument());
    expect(api.undoApply).toHaveBeenCalledTimes(1);
  });

  it("shows a generic error and keeps the entry visible when undo fails for another reason", async () => {
    vi.mocked(api.getApplyHistory).mockResolvedValue({ entries: [entry({ id: 2, is_undoable: true })] });
    vi.mocked(api.undoApply).mockRejectedValue(new Error("Bu geziyi düzenleme yetkin yok."));
    render(<ApplyHistoryPage />);
    await waitFor(() => expect(screen.getByText("Geri Al")).toBeInTheDocument());

    fireEvent.click(screen.getByText("Geri Al"));
    fireEvent.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Geri Al" }));

    await waitFor(() => expect(screen.getByText("Bu geziyi düzenleme yetkin yok.")).toBeInTheDocument());
    expect(screen.getAllByText("Geri Al").length).toBeGreaterThan(0);
  });
});
