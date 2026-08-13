import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import LoginPage from "./page";
import * as api from "@/lib/api";

const push = vi.fn();
const router = { push };
vi.mock("next/navigation", () => ({
  useRouter: () => router,
  useSearchParams: () => ({ get: () => null }),
}));

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, login: vi.fn(), saveAuthTokens: vi.fn() };
});

beforeEach(() => {
  vi.clearAllMocks();
  push.mockClear();
  delete process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID;
});

afterEach(() => {
  delete process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID;
});

describe("LoginPage", () => {
  it("links to the forgot-password page", () => {
    render(<LoginPage />);
    expect(screen.getByRole("link", { name: "Şifremi unuttum" })).toHaveAttribute("href", "/forgot-password");
  });

  it("prevents a re-entrant login submission while one is already in flight", async () => {
    let resolveLogin: (v: Awaited<ReturnType<typeof api.login>>) => void = () => {};
    vi.mocked(api.login).mockReturnValue(new Promise((resolve) => { resolveLogin = resolve; }));
    render(<LoginPage />);

    fireEvent.change(screen.getByLabelText("E-posta"), { target: { value: "u@test.com" } });
    fireEvent.change(screen.getByLabelText("Şifre"), { target: { value: "pass1234" } });
    const button = screen.getByRole("button", { name: /Giriş Yap/ });
    fireEvent.click(button);
    fireEvent.click(button);

    resolveLogin({ access_token: "t", refresh_token: "r", user_id: 1, email: "u@test.com" });
    await waitFor(() => expect(api.login).toHaveBeenCalledTimes(1));
  });

  it("does not render the Google sign-in button when NEXT_PUBLIC_GOOGLE_CLIENT_ID is unset", () => {
    render(<LoginPage />);
    expect(screen.queryByRole("button", { name: /Google ile devam et/ })).not.toBeInTheDocument();
  });

  it("renders the Google sign-in button when NEXT_PUBLIC_GOOGLE_CLIENT_ID is configured", () => {
    process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID = "test-client-id";
    render(<LoginPage />);
    expect(screen.getByRole("button", { name: /Google ile devam et/ })).toBeInTheDocument();
  });
});
