import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import ResetPasswordPage from "./page";
import * as api from "@/lib/api";

const push = vi.fn();
const router = { push };
let tokenParam: string | null = "valid-token";
vi.mock("next/navigation", () => ({
  useRouter: () => router,
  useSearchParams: () => ({ get: (key: string) => (key === "token" ? tokenParam : null) }),
}));

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, resetPassword: vi.fn() };
});

beforeEach(() => {
  vi.clearAllMocks();
  tokenParam = "valid-token";
});

describe("ResetPasswordPage", () => {
  it("submits the new password with the token from the URL and redirects to /login on success", async () => {
    vi.mocked(api.resetPassword).mockResolvedValue(undefined);
    render(<ResetPasswordPage />);

    fireEvent.change(screen.getByLabelText("Yeni Şifre"), { target: { value: "NewSecure123!" } });
    fireEvent.change(screen.getByLabelText("Yeni Şifre (Tekrar)"), { target: { value: "NewSecure123!" } });
    fireEvent.click(screen.getByRole("button", { name: /Şifreyi Güncelle/ }));

    await waitFor(() => expect(api.resetPassword).toHaveBeenCalledWith("valid-token", "NewSecure123!"));
    await waitFor(() => expect(screen.getByText(/Şifreniz güncellendi/)).toBeInTheDocument());
  });

  it("rejects mismatched passwords client-side without calling the API", () => {
    render(<ResetPasswordPage />);

    fireEvent.change(screen.getByLabelText("Yeni Şifre"), { target: { value: "NewSecure123!" } });
    fireEvent.change(screen.getByLabelText("Yeni Şifre (Tekrar)"), { target: { value: "Different123!" } });
    fireEvent.click(screen.getByRole("button", { name: /Şifreyi Güncelle/ }));

    expect(screen.getByText("Şifreler eşleşmiyor.")).toBeInTheDocument();
    expect(api.resetPassword).not.toHaveBeenCalled();
  });

  it("shows the server's error message and lets the user request a new link when the token is expired/used/invalid", async () => {
    vi.mocked(api.resetPassword).mockRejectedValue(new Error("Bu şifre sıfırlama linkinin süresi doldu. Yeni bir istek gönderin."));
    render(<ResetPasswordPage />);

    fireEvent.change(screen.getByLabelText("Yeni Şifre"), { target: { value: "NewSecure123!" } });
    fireEvent.change(screen.getByLabelText("Yeni Şifre (Tekrar)"), { target: { value: "NewSecure123!" } });
    fireEvent.click(screen.getByRole("button", { name: /Şifreyi Güncelle/ }));

    await waitFor(() => expect(screen.getByText(/süresi doldu/)).toBeInTheDocument());
  });

  it("disables the form and shows a warning when no token is present in the URL", () => {
    tokenParam = null;
    render(<ResetPasswordPage />);

    expect(screen.getByText(/Bu link geçersiz/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Şifreyi Güncelle/ })).toBeDisabled();
  });
});
