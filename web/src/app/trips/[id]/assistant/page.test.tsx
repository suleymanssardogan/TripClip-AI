import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import TripAssistantPage from "./page";
import * as api from "@/lib/api";

const push = vi.fn();
const router = { push };
vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "1" }),
  useRouter: () => router,
  usePathname: () => "/trips/1/assistant",
}));

vi.mock("@/components/Navbar", () => ({ default: () => null }));

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, getTrip: vi.fn(), askTripAssistant: vi.fn() };
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
  sessionStorage.clear();
});

describe("TripAssistantPage", () => {
  it("shows suggested prompts before any message is sent", async () => {
    vi.mocked(api.getTrip).mockResolvedValue(trip());
    render(<TripAssistantPage />);
    await waitFor(() => expect(screen.getByText("Bugünü özetle")).toBeInTheDocument());
  });

  it("clicking a suggested prompt sends it as a message", async () => {
    vi.mocked(api.getTrip).mockResolvedValue(trip());
    vi.mocked(api.askTripAssistant).mockResolvedValue({ answer: "Bugün Ayasofya'ya gideceksin.", references: [] });
    render(<TripAssistantPage />);
    await waitFor(() => expect(screen.getByText("Bugünü özetle")).toBeInTheDocument());

    fireEvent.click(screen.getByText("Bugünü özetle"));
    expect(screen.getByText("Bugünü özetle", { selector: "div" })).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText("Bugün Ayasofya'ya gideceksin.")).toBeInTheDocument());
    expect(api.askTripAssistant).toHaveBeenCalledWith(1, { message: "Bugünü özetle", history: [] });
  });

  it("sends a typed message via the form and clears the input", async () => {
    vi.mocked(api.getTrip).mockResolvedValue(trip());
    vi.mocked(api.askTripAssistant).mockResolvedValue({ answer: "Cevap", references: [] });
    render(<TripAssistantPage />);
    await waitFor(() => expect(screen.getByLabelText("Asistana mesaj yaz")).toBeInTheDocument());

    fireEvent.change(screen.getByLabelText("Asistana mesaj yaz"), { target: { value: "Kaç durak var?" } });
    fireEvent.click(screen.getByLabelText("Gönder"));

    expect(screen.getByLabelText("Asistana mesaj yaz")).toHaveValue("");
    await waitFor(() => expect(screen.getByText("Cevap")).toBeInTheDocument());
  });

  it("does not send an empty or whitespace-only message", async () => {
    vi.mocked(api.getTrip).mockResolvedValue(trip());
    render(<TripAssistantPage />);
    await waitFor(() => expect(screen.getByLabelText("Gönder")).toBeInTheDocument());
    expect(screen.getByLabelText("Gönder")).toBeDisabled();

    fireEvent.change(screen.getByLabelText("Asistana mesaj yaz"), { target: { value: "   " } });
    expect(screen.getByLabelText("Gönder")).toBeDisabled();
  });

  it("shows a loading indicator while waiting for a response", async () => {
    vi.mocked(api.getTrip).mockResolvedValue(trip());
    let resolveAsk: (v: api.AssistantResponse) => void = () => {};
    vi.mocked(api.askTripAssistant).mockReturnValue(new Promise((resolve) => { resolveAsk = resolve; }));
    render(<TripAssistantPage />);
    await waitFor(() => expect(screen.getByText("Bugünü özetle")).toBeInTheDocument());

    fireEvent.click(screen.getByText("Bugünü özetle"));
    await waitFor(() => expect(screen.getByText("Düşünüyor…")).toBeInTheDocument());
    expect(screen.getByLabelText("Gönder")).toBeDisabled();

    resolveAsk({ answer: "Cevap", references: [] });
    await waitFor(() => expect(screen.queryByText("Düşünüyor…")).not.toBeInTheDocument());
  });

  it("shows an error and offers retry when the request fails, without losing the input", async () => {
    vi.mocked(api.getTrip).mockResolvedValue(trip());
    vi.mocked(api.askTripAssistant).mockRejectedValueOnce(new Error("AI asistanı şu anda kullanılamıyor."));
    render(<TripAssistantPage />);
    await waitFor(() => expect(screen.getByLabelText("Asistana mesaj yaz")).toBeInTheDocument());

    fireEvent.change(screen.getByLabelText("Asistana mesaj yaz"), { target: { value: "soru" } });
    fireEvent.click(screen.getByLabelText("Gönder"));

    await waitFor(() => expect(screen.getByText("AI asistanı şu anda kullanılamıyor.")).toBeInTheDocument());
    // Başarısız kullanıcı mesajı sohbette KALMAMALI (yeniden gönderilecek) —
    // yalnızca hata + Tekrar Dene görünür.
    expect(screen.getByText("Tekrar Dene")).toBeInTheDocument();

    vi.mocked(api.askTripAssistant).mockResolvedValueOnce({ answer: "Bu sefer çalıştı.", references: [] });
    fireEvent.click(screen.getByText("Tekrar Dene"));
    await waitFor(() => expect(screen.getByText("Bu sefer çalıştı.")).toBeInTheDocument());
  });

  it("renders a clickable reference chip that navigates to Trip Detail with focus params", async () => {
    vi.mocked(api.getTrip).mockResolvedValue(trip());
    vi.mocked(api.askTripAssistant).mockResolvedValue({
      answer: "İlk durağın Ayasofya.",
      references: [{ type: "stop", day_index: 0, place_id: 1 }],
    });
    render(<TripAssistantPage />);
    await waitFor(() => expect(screen.getByText("Bugünü özetle")).toBeInTheDocument());
    fireEvent.click(screen.getByText("Bugünü özetle"));

    await waitFor(() => expect(screen.getByRole("button", { name: /Ayasofya/ })).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: /Ayasofya/ }));
    expect(push).toHaveBeenCalledWith("/trips/1?focusDay=0&focusPlace=1");
  });

  it("bounds the conversation history sent to the server", async () => {
    vi.mocked(api.getTrip).mockResolvedValue(trip());
    vi.mocked(api.askTripAssistant).mockResolvedValue({ answer: "ok", references: [] });
    render(<TripAssistantPage />);
    await waitFor(() => expect(screen.getByLabelText("Asistana mesaj yaz")).toBeInTheDocument());

    for (let i = 0; i < 8; i++) {
      fireEvent.change(screen.getByLabelText("Asistana mesaj yaz"), { target: { value: `soru ${i}` } });
      fireEvent.click(screen.getByLabelText("Gönder"));
      await waitFor(() => expect(api.askTripAssistant).toHaveBeenCalledTimes(i + 1));
    }

    const lastCall = vi.mocked(api.askTripAssistant).mock.calls.at(-1);
    expect(lastCall?.[1].history?.length).toBeLessThanOrEqual(6);
  });

  it("follow-up questions carry prior turns as history, and all messages stay visible", async () => {
    vi.mocked(api.getTrip).mockResolvedValue(trip());
    vi.mocked(api.askTripAssistant).mockResolvedValueOnce({ answer: "Bugün 4 durağın var.", references: [] });
    render(<TripAssistantPage />);
    await waitFor(() => expect(screen.getByLabelText("Asistana mesaj yaz")).toBeInTheDocument());

    fireEvent.change(screen.getByLabelText("Asistana mesaj yaz"), { target: { value: "Bugün hangi yerleri gezeceğim?" } });
    fireEvent.click(screen.getByLabelText("Gönder"));
    await waitFor(() => expect(screen.getByText("Bugün 4 durağın var.")).toBeInTheDocument());

    vi.mocked(api.askTripAssistant).mockResolvedValueOnce({ answer: "Zeugma Mozaik Müzesi.", references: [] });
    fireEvent.change(screen.getByLabelText("Asistana mesaj yaz"), { target: { value: "Peki bunlardan hangisi müze?" } });
    fireEvent.click(screen.getByLabelText("Gönder"));
    await waitFor(() => expect(screen.getByText("Zeugma Mozaik Müzesi.")).toBeInTheDocument());

    // Önceki tur hâlâ görünür — takip sorusu sohbeti SİLMEDİ.
    expect(screen.getByText("Bugün hangi yerleri gezeceğim?")).toBeInTheDocument();
    expect(screen.getByText("Bugün 4 durağın var.")).toBeInTheDocument();
    expect(screen.getByText("Peki bunlardan hangisi müze?")).toBeInTheDocument();

    const secondCall = vi.mocked(api.askTripAssistant).mock.calls[1];
    expect(secondCall[1]).toEqual({
      message: "Peki bunlardan hangisi müze?",
      history: [
        { role: "user", content: "Bugün hangi yerleri gezeceğim?" },
        { role: "assistant", content: "Bugün 4 durağın var." },
      ],
    });
  });

  it("shows an error state with retry when the trip itself fails to load", async () => {
    vi.mocked(api.getTrip).mockRejectedValue(new Error("Bu geziye erişimin yok."));
    render(<TripAssistantPage />);
    await waitFor(() => expect(screen.getByText("Bu geziye erişimin yok.")).toBeInTheDocument());
  });

  // M38 regression: bir referans çipine dokunmak `focusStop()` üzerinden
  // TAMAMEN FARKLI bir route'a (`/trips/[id]`) yönlendirir — bu, bu sayfa
  // bileşenini unmount eder. "AI Asistan"a geri dönmek YENİ bir
  // `TripAssistantPage` mount eder. Önceden `messages` sıfırdan `[]`e
  // başlıyor, TÜM sohbet geçmişi kayboluyordu (iOS'un M35'te bulup
  // düzeltmiş olduğu AYNI hata sınıfı, Web'e hiç taşınmamıştı). Gerçek
  // navigasyonu tekrarlamanın en yakın deterministik yolu: unmount edip
  // YENİDEN render etmek (React Testing Library'nin kendi `unmount()`'u).
  it("preserves the conversation across an unmount/remount cycle (reference-chip navigation away and back)", async () => {
    vi.mocked(api.getTrip).mockResolvedValue(trip());
    vi.mocked(api.askTripAssistant).mockResolvedValue({
      answer: "İlk durağın Ayasofya.",
      references: [{ type: "stop", day_index: 0, place_id: 1 }],
    });

    const { unmount } = render(<TripAssistantPage />);
    await waitFor(() => expect(screen.getByText("Bugünü özetle")).toBeInTheDocument());
    fireEvent.click(screen.getByText("Bugünü özetle"));
    await waitFor(() => expect(screen.getByText("İlk durağın Ayasofya.")).toBeInTheDocument());

    // Referans çipine dokunup Trip Detail'e giden kullanıcıyı simüle eder —
    // bu sayfa unmount edilir (gerçek navigasyonda olduğu gibi).
    unmount();

    // "AI Asistan"a geri dönmek — YENİ bir TripAssistantPage mount edilir.
    render(<TripAssistantPage />);
    await waitFor(() => expect(screen.getByText("İlk durağın Ayasofya.")).toBeInTheDocument());
    expect(screen.getByText("Bugünü özetle", { selector: "div" })).toBeInTheDocument();
    // Boş-sohbet "önerilen sorular" ekranı bir daha GÖRÜNMEMELİ — geçmiş var.
    expect(screen.queryByText("Bu gezi hakkında bana soru sorabilirsin")).not.toBeInTheDocument();
  });
});
