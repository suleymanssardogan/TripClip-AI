import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import ForgotPasswordPage from "./page";
import * as api from "@/lib/api";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, forgotPassword: vi.fn() };
});

beforeEach(() => {
  vi.clearAllMocks();
});

describe("ForgotPasswordPage", () => {
  it("shows the same generic success message whether the account exists or not (anti-enumeration)", async () => {
    vi.mocked(api.forgotPassword).mockResolvedValue(undefined);
    render(<ForgotPasswordPage />);

    fireEvent.change(screen.getByLabelText("E-posta"), { target: { value: "exists@test.com" } });
    fireEvent.click(screen.getByRole("button", { name: /Sıfırlama Linki Gönder/ }));

    await waitFor(() => expect(screen.getByText(/Bu e-posta adresine kayıtlı bir hesap varsa/)).toBeInTheDocument());
    expect(api.forgotPassword).toHaveBeenCalledWith("exists@test.com");
  });

  it("still shows the generic success message even when the request fails (never leaks account existence via error state)", async () => {
    vi.mocked(api.forgotPassword).mockRejectedValue(new Error("network down"));
    render(<ForgotPasswordPage />);

    fireEvent.change(screen.getByLabelText("E-posta"), { target: { value: "x@test.com" } });
    fireEvent.click(screen.getByRole("button", { name: /Sıfırlama Linki Gönder/ }));

    await waitFor(() => expect(screen.getByText(/Bu e-posta adresine kayıtlı bir hesap varsa/)).toBeInTheDocument());
  });

  it("prevents a re-entrant submission while one is already in flight", async () => {
    let resolveReq: () => void = () => {};
    vi.mocked(api.forgotPassword).mockReturnValue(new Promise((resolve) => { resolveReq = resolve; }));
    render(<ForgotPasswordPage />);

    fireEvent.change(screen.getByLabelText("E-posta"), { target: { value: "x@test.com" } });
    const button = screen.getByRole("button", { name: /Sıfırlama Linki Gönder/ });
    fireEvent.click(button);
    fireEvent.click(button);

    resolveReq();
    await waitFor(() => expect(screen.getByText(/Bu e-posta adresine kayıtlı bir hesap varsa/)).toBeInTheDocument());
    expect(api.forgotPassword).toHaveBeenCalledTimes(1);
  });
});
