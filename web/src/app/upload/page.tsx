"use client";

import React, {
  useState, useRef, useCallback, useEffect, DragEvent, ChangeEvent,
} from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Upload, Link2, AlertCircle, Video, CheckCircle2, X, Loader2,
} from "lucide-react";
import { useRouter } from "next/navigation";
import Navbar from "@/components/Navbar";
import { uploadVideo, queueUrl } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Card } from "@/components/ui/Card";

// ─── Constants ──────────────────────────────────────────────────────────────

const MAX_BYTES = 200 * 1024 * 1024; // 200 MB
const ACCEPTED_TYPES = ["video/mp4", "video/quicktime", "video/x-msvideo", "video/webm"];

// Same pattern as core-api validator
const SUPPORTED_URL_RE =
  /instagram\.com\/(reel|p|tv)\/|instagr\.am|youtube\.com\/|youtu\.be\/|\.mp4$/i;

// ─── Helpers ─────────────────────────────────────────────────────────────────

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
}

function validateFile(file: File): string | null {
  if (!ACCEPTED_TYPES.includes(file.type) && !file.name.match(/\.(mp4|mov|avi|webm)$/i)) {
    return "Yalnızca video dosyaları kabul edilir (MP4, MOV, AVI, WebM).";
  }
  if (file.size > MAX_BYTES) {
    return `Dosya çok büyük: ${formatBytes(file.size)}. Maksimum 200 MB.`;
  }
  return null;
}

function validateUrl(url: string): string | null {
  const trimmed = url.trim();
  if (!trimmed) return "Lütfen bir link girin.";
  if (!SUPPORTED_URL_RE.test(trimmed)) {
    return "Yalnızca Instagram Reels, YouTube ve doğrudan MP4 linkleri desteklenmektedir.";
  }
  return null;
}

// ─── Sub-components ───────────────────────────────────────────────────────────

type Mode = "file" | "url";

interface TabProps {
  active: boolean;
  onClick: () => void;
  icon: React.ReactNode;
  label: string;
}

function Tab({ active, onClick, icon, label }: TabProps) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-2 px-5 py-2.5 rounded-md text-sm font-semibold transition-all ${
        active
          ? "bg-accent/10 text-accent-text border border-accent/25"
          : "text-text-secondary hover:text-text hover:bg-surface2 border border-transparent"
      }`}
    >
      {icon}
      {label}
    </button>
  );
}

interface ErrorBannerProps { message: string; onDismiss: () => void; }

function ErrorBanner({ message, onDismiss }: ErrorBannerProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: -8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8 }}
      className="flex items-start gap-3 bg-destructive/10 border border-destructive/25 text-destructive
        px-4 py-3.5 rounded-md text-sm"
      role="alert"
      aria-live="assertive"
    >
      <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" aria-hidden />
      <span className="flex-1">{message}</span>
      <button
        onClick={onDismiss}
        className="flex-shrink-0 hover:opacity-70 transition-opacity"
        aria-label="Hatayı kapat"
      >
        <X className="w-3.5 h-3.5" />
      </button>
    </motion.div>
  );
}

// ─── Drop Zone ───────────────────────────────────────────────────────────────

interface DropZoneProps {
  file: File | null;
  onFile: (f: File) => void;
  onClear: () => void;
  disabled: boolean;
}

function DropZone({ file, onFile, onClear, disabled }: DropZoneProps) {
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleDrop = useCallback((e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragging(false);
    const dropped = e.dataTransfer.files[0];
    if (dropped) onFile(dropped);
  }, [onFile]);

  const handleChange = (e: ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files?.[0];
    if (selected) onFile(selected);
    e.target.value = "";
  };

  if (file) {
    return (
      <div className="relative flex items-center gap-4 p-5 bg-accent/5 border border-accent/20 rounded-lg">
        <div className="w-12 h-12 rounded-md bg-accent/10 flex items-center justify-center flex-shrink-0">
          <Video className="w-6 h-6 text-accent-text" aria-hidden />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-text text-sm font-semibold truncate">{file.name}</p>
          <p className="text-text-tertiary text-xs mt-0.5">{formatBytes(file.size)}</p>
        </div>
        {!disabled && (
          <button
            onClick={onClear}
            className="flex-shrink-0 p-1.5 rounded-sm hover:bg-surface2 text-text-tertiary hover:text-destructive transition-colors"
            aria-label="Dosyayı kaldır"
          >
            <X className="w-4 h-4" />
          </button>
        )}
      </div>
    );
  }

  return (
    <div
      onDragOver={(e) => { e.preventDefault(); if (!disabled) setDragging(true); }}
      onDragLeave={() => setDragging(false)}
      onDrop={disabled ? undefined : handleDrop}
      onClick={() => !disabled && inputRef.current?.click()}
      role="button"
      tabIndex={disabled ? -1 : 0}
      aria-label="Video dosyası seç ya da buraya sürükle"
      onKeyDown={(e) => { if (!disabled && (e.key === "Enter" || e.key === " ")) inputRef.current?.click(); }}
      className={`
        relative flex flex-col items-center justify-center gap-4 p-10
        rounded-lg border-[1.5px] border-dashed cursor-pointer select-none
        transition-all duration-200
        ${disabled
          ? "border-border opacity-50 cursor-not-allowed"
          : dragging
            ? "border-accent-text bg-accent/[0.06]"
            : "border-border-strong hover:border-accent/40 hover:bg-surface2/50"
        }
      `}
    >
      <div className={`w-14 h-14 rounded-full flex items-center justify-center transition-colors
        ${dragging ? "bg-accent/20" : "bg-surface2"}`}>
        <Upload className={`w-6 h-6 ${dragging ? "text-accent-text" : "text-text-tertiary"}`} aria-hidden />
      </div>

      <div className="text-center">
        <p className="text-text font-semibold">
          {dragging ? "Bırakabilirsiniz" : "Dosyayı buraya sürükleyin"}
        </p>
        <p className="text-text-secondary text-sm mt-1">veya tıklayarak seçin</p>
        <p className="text-text-tertiary text-xs mt-2">MP4, MOV, AVI, WebM · Maks. 200 MB</p>
      </div>

      <input
        ref={inputRef}
        type="file"
        accept="video/*"
        className="sr-only"
        onChange={handleChange}
        disabled={disabled}
        aria-hidden
      />
    </div>
  );
}

// ─── Upload Progress ──────────────────────────────────────────────────────────

function UploadProgress({ percent }: { percent: number }) {
  return (
    <div className="space-y-3" role="status" aria-live="polite" aria-label={`Yükleme: %${percent}`}>
      <div className="flex items-center justify-between text-sm">
        <span className="text-text-secondary flex items-center gap-2">
          <Loader2 className="w-4 h-4 animate-spin text-accent-text" aria-hidden />
          Sunucuya yükleniyor…
        </span>
        <span className="font-mono text-accent-text font-semibold tabular-nums">%{percent}</span>
      </div>
      <div className="h-1.5 bg-surface2 rounded-full overflow-hidden">
        <div
          className="h-full bg-accent rounded-full transition-all duration-300"
          style={{ width: `${percent}%` }}
        />
      </div>
      <p className="text-text-tertiary text-xs">Sayfa kapatılmayın, yükleme devam ediyor.</p>
    </div>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function UploadPage() {
  const router = useRouter();

  // Auth guard
  useEffect(() => {
    if (typeof window !== "undefined" && !localStorage.getItem("token")) {
      router.replace("/login");
    }
  }, [router]);

  const [mode, setMode]       = useState<Mode>("file");
  const [file, setFile]       = useState<File | null>(null);
  const [url, setUrl]         = useState("");
  const [error, setError]     = useState("");
  const [uploading, setUploading] = useState(false);
  const [uploadPct, setUploadPct] = useState(0);

  const clearError = () => setError("");

  // ── File Mode: submit ─────────────────────────────────────────────────────

  const handleFileSubmit = async () => {
    if (!file) return;
    const validationErr = validateFile(file);
    if (validationErr) { setError(validationErr); return; }

    setUploading(true);
    setError("");

    try {
      const { id } = await uploadVideo(file, (pct) => setUploadPct(pct));
      router.push(`/analyze/${id}`);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Yükleme sırasında bir hata oluştu.");
      setUploading(false);
      setUploadPct(0);
    }
  };

  // ── URL Mode: submit ──────────────────────────────────────────────────────

  const handleUrlSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const validationErr = validateUrl(url);
    if (validationErr) { setError(validationErr); return; }

    setUploading(true);
    setError("");

    try {
      const { id } = await queueUrl(url.trim());
      router.push(`/analyze/${id}`);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Kuyruğa alınırken bir hata oluştu.");
      setUploading(false);
    }
  };

  // ── File selection with instant validation ────────────────────────────────

  const handleFileSelected = (f: File) => {
    const validationErr = validateFile(f);
    if (validationErr) {
      setError(validationErr);
      setFile(null);
    } else {
      setError("");
      setFile(f);
    }
  };

  // ─────────────────────────────────────────────────────────────────────────

  return (
    <div className="min-h-screen bg-bg">
      <Navbar />

      <main className="relative pt-28 pb-24 px-4 sm:px-6 max-w-2xl mx-auto">

        {/* ── Header ─────────────────────────────────────────────────────── */}
        <motion.div
          initial={{ opacity: 0, y: -16 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-10"
        >
          <p className="font-mono text-xs text-text-tertiary tracking-widest uppercase mb-2">
            Gezi Analizi
          </p>
          <h1 className="font-display font-black text-3xl text-text">Video Yükle</h1>
          <p className="text-text-secondary text-sm mt-2">
            Video dosyanızı yükleyin veya bir Instagram / YouTube linki yapıştırın.
            AI, konumları otomatik çıkarır ve gezi planı oluşturur.
          </p>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.08 }}
          className="bg-surface border border-border rounded-lg p-6 sm:p-8 space-y-6"
        >
          {/* ── Mode Tabs ──────────────────────────────────────────────── */}
          <div className="flex gap-2" role="tablist" aria-label="Yükleme yöntemi">
            <Tab
              active={mode === "file"}
              onClick={() => { setMode("file"); clearError(); }}
              icon={<Upload className="w-4 h-4" aria-hidden />}
              label="Dosya Yükle"
            />
            <Tab
              active={mode === "url"}
              onClick={() => { setMode("url"); clearError(); }}
              icon={<Link2 className="w-4 h-4" aria-hidden />}
              label="Instagram / YouTube"
            />
          </div>

          {/* ── Error banner ───────────────────────────────────────────── */}
          <AnimatePresence>
            {error && <ErrorBanner message={error} onDismiss={clearError} />}
          </AnimatePresence>

          {/* ── Content ────────────────────────────────────────────────── */}
          <AnimatePresence mode="wait">

            {/* File mode */}
            {mode === "file" && (
              <motion.div
                key="file"
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -8 }}
                transition={{ duration: 0.18 }}
                className="space-y-5"
              >
                {uploading ? (
                  <UploadProgress percent={uploadPct} />
                ) : (
                  <>
                    <DropZone
                      file={file}
                      onFile={handleFileSelected}
                      onClear={() => { setFile(null); clearError(); }}
                      disabled={uploading}
                    />

                    <Button
                      onClick={handleFileSubmit}
                      disabled={!file || uploading}
                      className="w-full py-4 text-sm"
                      aria-label="Videoyu yükle ve analiz başlat"
                    >
                      <Upload className="w-4 h-4" aria-hidden />
                      Yükle ve Analiz Başlat
                    </Button>
                  </>
                )}
              </motion.div>
            )}

            {/* URL mode */}
            {mode === "url" && (
              <motion.div
                key="url"
                initial={{ opacity: 0, x: 8 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: 8 }}
                transition={{ duration: 0.18 }}
              >
                <form onSubmit={handleUrlSubmit} className="space-y-5" noValidate>
                  <div>
                    <label
                      htmlFor="video-url"
                      className="font-mono text-xs text-text-tertiary uppercase tracking-widest block mb-2"
                    >
                      Video Linki
                    </label>
                    <Input
                      id="video-url"
                      type="url"
                      value={url}
                      onChange={(e) => { setUrl(e.target.value); clearError(); }}
                      placeholder="https://www.instagram.com/reel/..."
                      disabled={uploading}
                      autoComplete="off"
                      spellCheck={false}
                      aria-describedby="url-hint"
                    />
                    <p id="url-hint" className="text-text-tertiary text-xs mt-2">
                      Instagram Reels, YouTube Shorts veya doğrudan MP4 linki desteklenmektedir.
                    </p>
                  </div>

                  <Button
                    type="submit"
                    disabled={!url.trim() || uploading}
                    className="w-full py-4 text-sm"
                    aria-label="Linki kuyruğa al ve analiz başlat"
                  >
                    {uploading ? (
                      <>
                        <Loader2 className="w-4 h-4 animate-spin" aria-hidden />
                        Kuyruğa Alınıyor…
                      </>
                    ) : (
                      <>
                        <CheckCircle2 className="w-4 h-4" aria-hidden />
                        Kuyruğa Al
                      </>
                    )}
                  </Button>
                </form>
              </motion.div>
            )}

          </AnimatePresence>
        </motion.div>

        {/* ── Info cards ──────────────────────────────────────────────────── */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.2 }}
          className="mt-6 grid grid-cols-3 gap-3 text-center"
          aria-label="Süreç adımları"
        >
          {[
            { step: "1", label: "Video veya link seç" },
            { step: "2", label: "AI analiz eder" },
            { step: "3", label: "Gezi planın hazır" },
          ].map(({ step, label }) => (
            <Card key={step} className="p-4">
              <div className="font-mono text-xs text-accent-text mb-2">0{step}</div>
              <p className="text-text-secondary text-xs leading-snug">{label}</p>
            </Card>
          ))}
        </motion.div>

      </main>
    </div>
  );
}
