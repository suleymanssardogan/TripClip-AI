"use client";

import React, { Suspense, useState } from "react";
import { motion } from "framer-motion";
import { Loader2, AlertCircle, CheckCircle, ArrowRight } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { register, saveAuthTokens } from "@/lib/api";
import PasswordInput from "@/components/PasswordInput";
import GoogleSignInButton from "@/components/GoogleSignInButton";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";

function SignupForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState("");
  const [success, setSuccess] = useState(false);

  // Yalnızca site-içi bir yola izin ver — açık yönlendirme (open redirect)
  // olmasın diye ("//evil.com" gibi protokolden bağımsız yollar da reddedilir).
  const next = searchParams.get("next");
  const redirectTo = next && next.startsWith("/") && !next.startsWith("//") ? next : "/welcome";
  const loginHref = next ? `/login?next=${encodeURIComponent(next)}` : "/login";

  const handleSignup = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (loading) return; // çift-tıklama/yeniden-giriş koruması
    setLoading(true); setError("");
    const fd = new FormData(e.currentTarget);
    try {
      const data = await register(
        fd.get("email") as string,
        fd.get("password") as string,
        fd.get("username") as string,
      );
      saveAuthTokens(data);
      setSuccess(true);
      setTimeout(() => router.push(redirectTo), 1000);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Kayıt sırasında bir hata oluştu.");
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
            <p className="font-mono text-xs text-text-tertiary uppercase tracking-widest mb-2">Başla</p>
            <h1 className="font-display font-black text-text text-3xl">Hesap Oluştur</h1>
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
              <span>Hesap oluşturuldu! Yönlendiriliyorsunuz…</span>
            </motion.div>
          )}

          <form onSubmit={handleSignup} className="space-y-5">
            {[
              { name: "username", label: "Kullanıcı Adı", type: "text",  ph: "gezgin_ali" },
              { name: "email",    label: "E-posta",        type: "email", ph: "sen@ornek.com" },
            ].map(field => (
              <div key={field.name}>
                <label htmlFor={field.name} className="font-mono text-xs text-text-tertiary uppercase tracking-widest block mb-2">
                  {field.label}
                </label>
                <Input
                  id={field.name} name={field.name} type={field.type} placeholder={field.ph}
                  required disabled={loading || success}
                />
              </div>
            ))}

            <div>
              <label htmlFor="password" className="font-mono text-xs text-text-tertiary uppercase tracking-widest block mb-2">
                Şifre
              </label>
              <PasswordInput
                id="password"
                name="password"
                placeholder="En az 8 karakter"
                required
                disabled={loading || success}
                autoComplete="new-password"
              />
            </div>

            <Button
              type="submit" disabled={loading || success}
              className="w-full py-3.5 mt-2"
            >
              {loading ? (
                <><Loader2 className="w-4 h-4 animate-spin" /> Oluşturuluyor…</>
              ) : (
                <><span>Hesap Oluştur</span><ArrowRight className="w-4 h-4" /></>
              )}
            </Button>
          </form>

          <GoogleSignInButton next={redirectTo} disabled={loading || success} />

          <div className="border-t border-border my-7" />

          <p className="text-text-secondary text-sm text-center">
            Zaten hesabın var mı?{" "}
            <Link href={loginHref} className="text-accent-text hover:opacity-80 font-semibold transition-opacity">
              Giriş Yap →
            </Link>
          </p>
        </motion.div>
      </div>
    </div>
  );
}

export default function SignupPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-bg" />}>
      <SignupForm />
    </Suspense>
  );
}
