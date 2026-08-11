"use client";

import { useEffect } from "react";
import { Button } from "./ui/Button";

interface ConfirmDialogProps {
  open: boolean;
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  /** Silme/geri alma gibi yıkıcı eylemler için — onay butonunu görsel olarak ayırt eder. */
  destructive?: boolean;
  busy?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

/**
 * Bu proje daha önce hiçbir modal/dialog bileşenine sahip değildi (Milestone
 * 21 — Web AI Trip Optimizer — kadar) — optimizer'ın kendi Uygula/Sil/Geri Al
 * onaylarının hepsinin ihtiyaç duyduğu tek, paylaşılan, erişilebilir bir
 * bileşen (bkz. docs/ios-trip-optimizer.md "Web AI Trip Optimizer" —
 * `TripDetailView`'ın kendi `.confirmationDialog` deseninin web karşılığı).
 */
export function ConfirmDialog({
  open, title, message, confirmLabel = "Onayla", cancelLabel = "Vazgeç",
  destructive = false, busy = false, onConfirm, onCancel,
}: ConfirmDialogProps) {
  useEffect(() => {
    if (!open) return;
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") onCancel();
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, onCancel]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[2000] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4"
      onClick={onCancel}
    >
      <div
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="confirm-dialog-title"
        aria-describedby="confirm-dialog-message"
        className="w-full max-w-sm bg-surface border border-border-strong rounded-lg p-6 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 id="confirm-dialog-title" className="font-display font-bold text-lg text-text mb-2">
          {title}
        </h2>
        <p id="confirm-dialog-message" className="text-sm text-text-secondary mb-6 leading-relaxed">
          {message}
        </p>
        <div className="flex justify-end gap-3">
          <Button variant="ghost" size="sm" onClick={onCancel} disabled={busy}>
            {cancelLabel}
          </Button>
          <Button
            variant={destructive ? "outline" : "primary"}
            size="sm"
            className={destructive ? "border-destructive/40 text-destructive hover:bg-destructive/10 hover:border-destructive/60" : undefined}
            onClick={onConfirm}
            disabled={busy}
            autoFocus
          >
            {busy ? "İşleniyor…" : confirmLabel}
          </Button>
        </div>
      </div>
    </div>
  );
}
