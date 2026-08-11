import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ConfirmDialog } from "./ConfirmDialog";

describe("ConfirmDialog", () => {
  it("renders nothing when closed", () => {
    render(
      <ConfirmDialog open={false} title="T" message="M" onConfirm={vi.fn()} onCancel={vi.fn()} />
    );
    expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
  });

  it("renders title/message and calls onConfirm/onCancel", () => {
    const onConfirm = vi.fn();
    const onCancel = vi.fn();
    render(
      <ConfirmDialog open title="Emin misin?" message="Geri alınamaz." onConfirm={onConfirm} onCancel={onCancel} />
    );
    expect(screen.getByRole("alertdialog")).toBeInTheDocument();
    expect(screen.getByText("Emin misin?")).toBeInTheDocument();
    expect(screen.getByText("Geri alınamaz.")).toBeInTheDocument();

    fireEvent.click(screen.getByText("Onayla"));
    expect(onConfirm).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByText("Vazgeç"));
    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it("closes on Escape key", () => {
    const onCancel = vi.fn();
    render(<ConfirmDialog open title="T" message="M" onConfirm={vi.fn()} onCancel={onCancel} />);
    fireEvent.keyDown(window, { key: "Escape" });
    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it("disables both buttons while busy", () => {
    render(<ConfirmDialog open title="T" message="M" busy onConfirm={vi.fn()} onCancel={vi.fn()} />);
    expect(screen.getByText("İşleniyor…").closest("button")).toBeDisabled();
    expect(screen.getByText("Vazgeç").closest("button")).toBeDisabled();
  });

  it("uses the custom confirm/cancel labels when provided", () => {
    render(
      <ConfirmDialog
        open title="T" message="M" confirmLabel="Geri Al" cancelLabel="İptal"
        onConfirm={vi.fn()} onCancel={vi.fn()}
      />
    );
    expect(screen.getByText("Geri Al")).toBeInTheDocument();
    expect(screen.getByText("İptal")).toBeInTheDocument();
  });
});
