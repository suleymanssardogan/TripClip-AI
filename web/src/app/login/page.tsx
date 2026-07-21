"use client";

import React, { useState } from "react";
import { motion } from "framer-motion";
import { Loader2, AlertCircle, CheckCircle, ArrowRight } from "lucide-react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { login, saveAuthTokens } from "@/lib/api";
import PasswordInput from "@/components/PasswordInput";

export default function LoginPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState("");
  const [success, setSuccess] = useState(false);

  const handleLogin = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setLoading(true); setError("");
    const fd = new FormData(e.currentTarget);
    try {
      const data = await login(fd.get("email") as string, fd.get("password") as string);
      saveAuthTokens(data);
      setSuccess(true);
      setTimeout(() => router.push("/dashboard"), 800);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "E-posta veya şifre hatalı.");
    } finally { setLoading(false); }
  };

  return (
    <div className="min-h-screen bg-bg flex items-center justify-center px-6">
      <div className="relative w-full max-w-md">
        {/* Logo */}
        <Link href="/" className="flex flex-col mb-10">
          <p className="font-display font-black text-text text-2xl tracking-tight">TripClip</p>
          <p className="font-mono text-[9px] font-semibold tracking-[0.25em] uppercase text-accent-text">AI Travel</p>
        </Link>

        <motion.div
          initial={{ opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, ease: "easeOut" }}
          className="bg-surface border border-border rounded-lg p-8"
        >
          {/* Başlık */}
          <div className="mb-8">
            <p className="font-mono text-xs text-text-tertiary uppercase tracking-widest mb-2">Hoş Geldin</p>
            <h1 className="font-display font-black text-text text-3xl">Giriş Yap</h1>
          </div>

          {/* Hata */}
          {error && (
            <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }}
              className="flex items-start gap-3 bg-destructive/10 border border-destructive/25
                text-destructive px-4 py-3.5 rounded-md mb-6 text-sm"
              role="alert" aria-live="assertive">
              <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
              <span>{error}</span>
            </motion.div>
          )}

          {/* Başarı */}
          {success && (
            <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }}
              className="flex items-center gap-3 bg-success/10 border border-success/25
                text-success px-4 py-3.5 rounded-md mb-6 text-sm">
              <CheckCircle className="w-4 h-4 flex-shrink-0" />
              <span>Giriş başarılı, yönlendiriliyorsunuz…</span>
            </motion.div>
          )}

          <form onSubmit={handleLogin} className="space-y-5">
            <div>
              <label className="font-mono text-xs text-text-tertiary uppercase tracking-widest block mb-2">
                E-posta
              </label>
              <input
                name="email" type="email" placeholder="sen@ornek.com"
                className="w-full bg-surface2 border border-border-strong rounded-md px-4 py-3.5
                  text-text placeholder:text-text-tertiary text-sm
                  focus:outline-none focus:border-accent-text transition-colors"
                required disabled={loading || success}
              />
            </div>
            <div>
              <label className="font-mono text-xs text-text-tertiary uppercase tracking-widest block mb-2">
                Şifre
              </label>
              <PasswordInput
                name="password"
                placeholder="••••••••"
                required
                disabled={loading || success}
                autoComplete="current-password"
              />
            </div>

            <button
              type="submit" disabled={loading || success}
              className="w-full flex items-center justify-center gap-2 bg-accent text-on-accent hover:bg-accent-hover transition-colors
                rounded-md py-3.5 mt-2 font-bold disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? (
                <><Loader2 className="w-4 h-4 animate-spin" /> Giriş yapılıyor…</>
              ) : (
                <><span>Giriş Yap</span><ArrowRight className="w-4 h-4" /></>
              )}
            </button>
          </form>

          <div className="border-t border-border my-7" />

          <p className="text-text-secondary text-sm text-center">
            Hesabın yok mu?{" "}
            <Link href="/signup" className="text-accent-text hover:opacity-80 font-semibold transition-opacity">
              Kaydol →
            </Link>
          </p>
        </motion.div>
      </div>
    </div>
  );
}
