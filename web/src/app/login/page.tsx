"use client";

import React, { Suspense, useState } from "react";
import { motion } from "framer-motion";
import { Loader2, AlertCircle, CheckCircle, ArrowRight } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { login } from "@/lib/api";
import PasswordInput from "@/components/PasswordInput";
import GoogleSignInButton from "@/components/GoogleSignInButton";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import AuthShell from "@/components/AuthShell";

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState("");
  const [success, setSuccess] = useState(false);

  // Yalnızca site-içi bir yola izin ver — açık yönlendirme (open redirect)
  // olmasın diye ("//evil.com" gibi protokolden bağımsız yollar da reddedilir).
  const next = searchParams.get("next");
  const redirectTo = next && next.startsWith("/") && !next.startsWith("//") ? next : "/dashboard";
  const signupHref = next ? `/signup?next=${encodeURIComponent(next)}` : "/signup";

  const handleLogin = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (loading) return; // çift-tıklama/yeniden-giriş koruması
    setLoading(true); setError("");
    const fd = new FormData(e.currentTarget);
    try {
      await login(fd.get("email") as string, fd.get("password") as string);
      setSuccess(true);
      setTimeout(() => router.push(redirectTo), 800);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "E-posta veya şifre hatalı.");
    } finally { setLoading(false); }
  };

  return (
    <AuthShell>
      <div className="relative w-full">
        {/* Logo */}
        <Link href="/" className="mb-8 flex items-center gap-2.5">
          <span className="font-display text-2xl font-bold tracking-[-0.05em] text-text">tripclip<span className="text-accent-text">.</span></span>
        </Link>

        <motion.div
          initial={{ opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, ease: "easeOut" }}
          className="rounded-lg border border-border bg-surface p-7 shadow-card sm:p-9"
        >
          {/* Başlık */}
          <div className="mb-8">
            <p className="mb-2 text-xs font-bold uppercase tracking-[0.18em] text-route">HOŞ GELDİN</p>
            <h1 className="font-display text-3xl font-bold tracking-[-0.045em] text-text">Yolculuğuna devam et.</h1>
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
              <label htmlFor="email" className="font-mono text-xs text-text-tertiary uppercase tracking-widest block mb-2">
                E-posta
              </label>
              <Input
                id="email" name="email" type="email" placeholder="sen@ornek.com"
                required disabled={loading || success}
              />
            </div>
            <div>
              <div className="flex items-center justify-between mb-2">
                <label htmlFor="password" className="font-mono text-xs text-text-tertiary uppercase tracking-widest">
                  Şifre
                </label>
                <Link href="/forgot-password" className="text-xs text-accent-text hover:opacity-80 font-semibold transition-opacity">
                  Şifremi unuttum
                </Link>
              </div>
              <PasswordInput
                id="password"
                name="password"
                placeholder="••••••••"
                required
                disabled={loading || success}
                autoComplete="current-password"
              />
            </div>

            <Button
              type="submit" disabled={loading || success}
              className="w-full py-3.5 mt-2"
            >
              {loading ? (
                <><Loader2 className="w-4 h-4 animate-spin" /> Giriş yapılıyor…</>
              ) : (
                <><span>Giriş Yap</span><ArrowRight className="w-4 h-4" /></>
              )}
            </Button>
          </form>

          <GoogleSignInButton next={redirectTo} disabled={loading || success} />

          <div className="border-t border-border my-7" />

          <p className="text-text-secondary text-sm text-center">
            Hesabın yok mu?{" "}
            <Link href={signupHref} className="text-accent-text hover:opacity-80 font-semibold transition-opacity">
              Kaydol →
            </Link>
          </p>
        </motion.div>
      </div>
    </AuthShell>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-bg" />}>
      <LoginForm />
    </Suspense>
  );
}
