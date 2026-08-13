import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import GoogleCallbackPage from "./page";
import * as api from "@/lib/api";

const push = vi.fn();
const router = { push };
let params: Record<string, string | null> = {};
vi.mock("next/navigation", () => ({
  useRouter: () => router,
  useSearchParams: () => ({ get: (key: string) => params[key] ?? null }),
}));

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, googleSignIn: vi.fn(), saveAuthTokens: vi.fn() };
});

const STATE_KEY = "tripclip_google_oauth_state";
const NEXT_KEY = "tripclip_google_oauth_next";

beforeEach(() => {
  vi.clearAllMocks();
  push.mockClear();
  params = {};
  sessionStorage.clear();
});

describe("GoogleCallbackPage", () => {
  it("exchanges the code for tokens and redirects to the stored `next` path when the OAuth state matches", async () => {
    sessionStorage.setItem(STATE_KEY, "abc123");
    sessionStorage.setItem(NEXT_KEY, "/dashboard");
    params = { code: "authcode", state: "abc123" };
    vi.mocked(api.googleSignIn).mockResolvedValue({
      access_token: "t", refresh_token: "r", user_id: 1, email: "g@test.com",
    });

    render(<GoogleCallbackPage />);

    await waitFor(() => expect(api.googleSignIn).toHaveBeenCalledWith("authcode", expect.stringContaining("/auth/google/callback")));
    await waitFor(() => expect(push).toHaveBeenCalledWith("/dashboard"));
    expect(api.saveAuthTokens).toHaveBeenCalled();
  });

  it("shows a safe error and never calls the API when the OAuth state does not match (CSRF protection)", async () => {
    sessionStorage.setItem(STATE_KEY, "expected-state");
    sessionStorage.setItem(NEXT_KEY, "/dashboard");
    params = { code: "authcode", state: "attacker-supplied-state" };

    render(<GoogleCallbackPage />);

    await waitFor(() => expect(screen.getByText(/Güvenlik doğrulaması başarısız oldu/)).toBeInTheDocument());
    expect(api.googleSignIn).not.toHaveBeenCalled();
  });

  // M38 fix: iptal artık genel hatalarla AYNI alarm verici kırmızı
  // `role="alert"` kutusuyla DEĞİL, nötr bir mesajla gösteriliyor —
  // kullanıcı bir şeyi BOZMADI, yalnızca rıza ekranını iptal etti.
  it("shows a neutral (non-alarming) cancellation message when Google itself returns an error param, without calling the API", async () => {
    params = { error: "access_denied" };

    render(<GoogleCallbackPage />);

    await waitFor(() => expect(screen.getByText("Google girişi iptal edildi.")).toBeInTheDocument());
    expect(api.googleSignIn).not.toHaveBeenCalled();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("shows the server's error message when the account-linking logic rejects the sign-in", async () => {
    sessionStorage.setItem(STATE_KEY, "abc123");
    sessionStorage.setItem(NEXT_KEY, "/dashboard");
    params = { code: "authcode", state: "abc123" };
    vi.mocked(api.googleSignIn).mockRejectedValue(new Error("Bu e-posta adresiyle zaten bir hesap mevcut. Lütfen e-posta/şifre ile giriş yapın."));

    render(<GoogleCallbackPage />);

    await waitFor(() => expect(screen.getByText(/zaten bir hesap mevcut/)).toBeInTheDocument());
  });
});
