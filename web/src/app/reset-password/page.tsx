"use client";

import React, { Suspense, useState } from "react";
import { motion } from "framer-motion";
import { Loader2, AlertCircle, CheckCircle, ArrowRight } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { resetPassword } from "@/lib/api";
import PasswordInput from "@/components/PasswordInput";
import { Button } from "@/components/ui/Button";

function ResetPasswordForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const token = searchParams.get("token");

  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState("");
  const [success, setSuccess] = useState(false);

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (loading) return;
    setError("");

    const fd = new FormData(e.currentTarget);
    const newPassword = fd.get("password") as string;
    const confirmPassword = fd.get("confirm_password") as string;

    if (newPassword !== confirmPassword) {
      setError("Şifreler eşleşmiyor.");
      return;
    }
    if (!token) {
      setError("Sıfırlama linki geçersiz. Lütfen yeni bir şifre sıfırlama isteği gönderin.");
      return;
    }

    setLoading(true);
    try {
      await resetPassword(token, newPassword);
      setSuccess(true);
      setTimeout(() => router.push("/login"), 1500);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Şifre sıfırlanamadı.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-bg flex items-center justify-center px-6">
      <div className="relative w-full max-w-md">
        <Link href="/" className="flex flex-col mb-10">
          <p className="font-display font-black text-text text-2xl tracking-tight">TripClip</p>
          <p className="font-mono text-[9px] font-semibold tracking-[0.25em] uppercase text-accent-text">AI Travel</p>
        </Link>

        <motion.div
          initial={{ opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, ease: "easeOut" }}
          className="bg-surface border border-border rounded-lg p-8"
        >
          <div className="mb-8">
            <p className="font-mono text-xs text-text-tertiary uppercase tracking-widest mb-2">Hesap Kurtarma</p>
            <h1 className="font-display font-black text-text text-3xl">Yeni Şifre Belirle</h1>
          </div>

          {!token && (
            <div className="flex items-start gap-3 bg-destructive/10 border border-destructive/25
              text-destructive px-4 py-3.5 rounded-md mb-6 text-sm" role="alert">
              <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
              <span>Bu link geçersiz. Lütfen e-postanızdaki linki tam olarak kullanın veya yeni bir istek gönderin.</span>
            </div>
          )}

          {error && (
            <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }}
              className="flex items-start gap-3 bg-destructive/10 border border-destructive/25
                text-destructive px-4 py-3.5 rounded-md mb-6 text-sm"
              role="alert" aria-live="assertive">
              <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
              <span>{error}</span>
            </motion.div>
          )}

          {success ? (
            <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }}
              className="flex items-center gap-3 bg-success/10 border border-success/25
                text-success px-4 py-3.5 rounded-md text-sm">
              <CheckCircle className="w-4 h-4 flex-shrink-0" />
              <span>Şifreniz güncellendi. Giriş sayfasına yönlendiriliyorsunuz…</span>
            </motion.div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-5">
              <div>
                <label htmlFor="password" className="font-mono text-xs text-text-tertiary uppercase tracking-widest block mb-2">
                  Yeni Şifre
                </label>
                <PasswordInput
                  id="password"
                  name="password"
                  placeholder="En az 8 karakter"
                  required
                  disabled={loading || !token}
                  autoComplete="new-password"
                />
              </div>
              <div>
                <label htmlFor="confirm_password" className="font-mono text-xs text-text-tertiary uppercase tracking-widest block mb-2">
                  Yeni Şifre (Tekrar)
                </label>
                <PasswordInput
                  id="confirm_password"
                  name="confirm_password"
                  placeholder="••••••••"
                  required
                  disabled={loading || !token}
                  autoComplete="new-password"
                />
              </div>

              <Button type="submit" disabled={loading || !token} className="w-full py-3.5 mt-2">
                {loading ? (
                  <><Loader2 className="w-4 h-4 animate-spin" /> Güncelleniyor…</>
                ) : (
                  <><span>Şifreyi Güncelle</span><ArrowRight className="w-4 h-4" /></>
                )}
              </Button>
            </form>
          )}

          <div className="border-t border-border my-7" />

          <p className="text-text-secondary text-sm text-center">
            <Link href="/forgot-password" className="text-accent-text hover:opacity-80 font-semibold transition-opacity">
              ← Yeni bir sıfırlama linki iste
            </Link>
          </p>
        </motion.div>
      </div>
    </div>
  );
}

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-bg" />}>
      <ResetPasswordForm />
    </Suspense>
  );
}
