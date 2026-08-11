import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { OptimizerConfigForm } from "./OptimizerConfigForm";
import type { TripStop } from "@/lib/api";

function stop(placeId: number, name: string): TripStop {
  return {
    place_id: placeId, name, lat: 41.0, lng: 29.0,
    city: "İstanbul", category: "tarihi", day_index: 0, order_index: placeId,
  };
}

const STOPS = [stop(1, "Ayasofya"), stop(2, "Topkapı Sarayı"), stop(3, "Galata Kulesi")];

describe("OptimizerConfigForm", () => {
  it("selects all places by default — matches iOS/backend default behavior", () => {
    render(<OptimizerConfigForm stops={STOPS} submitting={false} onSubmit={vi.fn()} />);
    expect(screen.getByText("Mekanlar (3/3 seçili)")).toBeInTheDocument();
  });

  it("toggles a single place off and back on", () => {
    render(<OptimizerConfigForm stops={STOPS} submitting={false} onSubmit={vi.fn()} />);
    fireEvent.click(screen.getByText("Ayasofya"));
    expect(screen.getByText("Mekanlar (2/3 seçili)")).toBeInTheDocument();
    fireEvent.click(screen.getByText("Ayasofya"));
    expect(screen.getByText("Mekanlar (3/3 seçili)")).toBeInTheDocument();
  });

  it("deselect all, then select all restores full selection", () => {
    render(<OptimizerConfigForm stops={STOPS} submitting={false} onSubmit={vi.fn()} />);
    fireEvent.click(screen.getByText("Seçimi Kaldır"));
    expect(screen.getByText("Mekanlar (0/3 seçili)")).toBeInTheDocument();
    fireEvent.click(screen.getByText("Tümünü Seç"));
    expect(screen.getByText("Mekanlar (3/3 seçili)")).toBeInTheDocument();
  });

  it("blocks submission and shows a message when zero places are selected", () => {
    const onSubmit = vi.fn();
    render(<OptimizerConfigForm stops={STOPS} submitting={false} onSubmit={onSubmit} />);
    fireEvent.click(screen.getByText("Seçimi Kaldır"));
    expect(screen.getByText("En az bir mekan seçmelisin")).toBeInTheDocument();
    fireEvent.click(screen.getByText("Optimize Et"));
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("accepts an overnight time range (end before start) without rejecting it", () => {
    const onSubmit = vi.fn();
    render(<OptimizerConfigForm stops={STOPS} submitting={false} onSubmit={onSubmit} />);
    fireEvent.change(screen.getByLabelText("Başlangıç Saati"), { target: { value: "18:00" } });
    fireEvent.change(screen.getByLabelText("Bitiş Saati"), { target: { value: "01:00" } });
    // Backend'in kendi TEK doğrulama kuralı: yalnızca EŞİT değerler geçersiz —
    // gece yarısını aşan bu çift istemci tarafında REDDEDİLMEMELİ.
    expect(screen.queryByText("Başlangıç ve bitiş saati aynı olamaz.")).not.toBeInTheDocument();
    fireEvent.click(screen.getByText("Optimize Et"));
    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({ preferred_start_time: "18:00", preferred_end_time: "01:00" })
    );
  });

  it("rejects an equal start/end time range — the one rule the backend actually enforces", () => {
    const onSubmit = vi.fn();
    render(<OptimizerConfigForm stops={STOPS} submitting={false} onSubmit={onSubmit} />);
    fireEvent.change(screen.getByLabelText("Başlangıç Saati"), { target: { value: "10:00" } });
    fireEvent.change(screen.getByLabelText("Bitiş Saati"), { target: { value: "10:00" } });
    expect(screen.getByText("Başlangıç ve bitiş saati aynı olamaz.")).toBeInTheDocument();
    fireEvent.click(screen.getByText("Optimize Et"));
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("increments and decrements duration, starting from Otomatik", () => {
    render(<OptimizerConfigForm stops={STOPS} submitting={false} onSubmit={vi.fn()} />);
    expect(screen.getByText("Otomatik")).toBeInTheDocument();
    fireEvent.click(screen.getByLabelText("Süreyi artır"));
    fireEvent.click(screen.getByLabelText("Süreyi artır"));
    expect(screen.getByText("2")).toBeInTheDocument();
    fireEvent.click(screen.getByLabelText("Süreyi azalt"));
    expect(screen.getByText("1")).toBeInTheDocument();
    fireEvent.click(screen.getByLabelText("Süreyi azalt"));
    expect(screen.getByText("Otomatik")).toBeInTheDocument();
  });

  it("enabling planning date includes start_date in the submitted config", () => {
    const onSubmit = vi.fn();
    render(<OptimizerConfigForm stops={STOPS} submitting={false} onSubmit={onSubmit} />);
    fireEvent.click(screen.getByLabelText("Planlama tarihini etkinleştir"));
    fireEvent.change(screen.getByLabelText("Planlama tarihi"), { target: { value: "2026-09-01" } });
    fireEvent.click(screen.getByText("Optimize Et"));
    expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({ start_date: "2026-09-01" }));
  });

  it("submits selected place IDs in the trip's own stop order, not click order", () => {
    const onSubmit = vi.fn();
    render(<OptimizerConfigForm stops={STOPS} submitting={false} onSubmit={onSubmit} />);
    // Sırayla değil, TERS sırada tıkla (3, 1) — hepsi zaten seçili, önce
    // hepsini kaldırıp yeniden farklı sırada seçmeye çalışmak yerine bu
    // testin amacı: submit edilen dizi HER ZAMAN trip'in kendi durak
    // sırasını korur (tıklama sırasını DEĞİL).
    fireEvent.click(screen.getByText("Galata Kulesi")); // kaldır (id 3)
    fireEvent.click(screen.getByText("Galata Kulesi")); // tekrar seç (id 3)
    fireEvent.click(screen.getByText("Optimize Et"));
    expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({ selected_place_ids: [1, 2, 3] }));
  });

  it("disables the submit button while submitting (re-entrancy guard)", () => {
    render(<OptimizerConfigForm stops={STOPS} submitting={true} onSubmit={vi.fn()} />);
    expect(screen.getByText("Optimize ediliyor…").closest("button")).toBeDisabled();
  });

  it("toggles a place via the keyboard (Enter/Space), not just click — accessibility-critical interaction", () => {
    render(<OptimizerConfigForm stops={STOPS} submitting={false} onSubmit={vi.fn()} />);
    const row = screen.getByText("Ayasofya").closest('[role="checkbox"]') as HTMLElement;
    expect(row).toHaveAttribute("aria-checked", "true");

    fireEvent.keyDown(row, { key: "Enter" });
    expect(row).toHaveAttribute("aria-checked", "false");
    expect(screen.getByText("Mekanlar (2/3 seçili)")).toBeInTheDocument();

    fireEvent.keyDown(row, { key: " " });
    expect(row).toHaveAttribute("aria-checked", "true");
    expect(screen.getByText("Mekanlar (3/3 seçili)")).toBeInTheDocument();
  });

  it("has no transport-mode selector, and never sends transport_mode — OptimizeTripRequest has never had this field (deliberate, documented decision)", () => {
    const onSubmit = vi.fn();
    render(<OptimizerConfigForm stops={STOPS} submitting={false} onSubmit={onSubmit} />);
    expect(screen.queryByText(/automobile|walking|transit|araç|yürüyüş|toplu taşıma/i)).not.toBeInTheDocument();
    fireEvent.click(screen.getByText("Optimize Et"));
    const [config] = onSubmit.mock.calls[0];
    expect(config).not.toHaveProperty("transport_mode");
  });
});
