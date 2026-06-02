"use client";

import React, { useState } from "react";
import { motion } from "framer-motion";
import { Loader2, AlertCircle, CheckCircle, ArrowRight } from "lucide-react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { register } from "@/lib/api";
import PasswordInput from "@/components/PasswordInput";

export default function SignupPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState("");
  const [success, setSuccess] = useState(false);

  const handleSignup = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setLoading(true); setError("");
    const fd = new FormData(e.currentTarget);
    try {
      const data = await register(
        fd.get("email") as string,
        fd.get("password") as string,
        fd.get("username") as string,
      );
      localStorage.setItem("token",   data.access_token);
      localStorage.setItem("user_id", String(data.user_id));
      localStorage.setItem("email",   fd.get("email") as string);
      setSuccess(true);
      setTimeout(() => router.push("/welcome"), 1000);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Kayıt sırasında bir hata oluştu.");
    } finally { setLoading(false); }
  };

  return (
    <div className="min-h-screen bg-bg flex items-center justify-center px-6 relative overflow-hidden">
      {/* Orbs */}
      <div className="fixed inset-0 pointer-events-none">
        <div className="orb w-[500px] h-[500px] bg-neon -top-40 -left-40" />
        <div className="orb w-[400px] h-[400px] bg-coral bottom-0 -right-32" />
      </div>

      <div className="relative w-full max-w-md">
        {/* Logo */}
        <Link href="/" className="flex flex-col mb-10">
          <p className="font-display font-black text-ice text-2xl tracking-tight">TripClip</p>
          <p className="text-[9px] font-semibold tracking-[0.25em] uppercase text-neon">AI Travel</p>
        </Link>

        <motion.div
          initial={{ opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, ease: "easeOut" }}
          className="neon-card rounded-2xl p-8"
        >
          {/* Başlık */}
          <div className="mb-8">
            <p className="text-xs font-mono text-neon/60 uppercase tracking-widest mb-2">Başla</p>
            <h1 className="font-display font-black text-ice text-3xl">Hesap Oluştur</h1>
          </div>

          {/* Hata */}
          {error && (
            <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }}
              className="flex items-start gap-3 bg-red-500/10 border border-red-500/25
                text-red-400 px-4 py-3.5 rounded-xl mb-6 text-sm">
              <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
              <span>{error}</span>
            </motion.div>
          )}

          {/* Başarı */}
          {success && (
            <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }}
              className="flex items-center gap-3 bg-neon/10 border border-neon/25
                text-neon px-4 py-3.5 rounded-xl mb-6 text-sm">
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
                <label className="text-xs font-mono text-neon/60 uppercase tracking-widest block mb-2">
                  {field.label}
                </label>
                <input
                  name={field.name} type={field.type} placeholder={field.ph}
                  className="w-full bg-white/[0.04] border border-white/10 rounded-xl px-4 py-3.5
                    text-ice placeholder:text-muted text-sm
                    focus:outline-none focus:border-neon/40 transition-colors"
                  required disabled={loading || success}
                />
              </div>
            ))}

            <div>
              <label className="text-xs font-mono text-neon/60 uppercase tracking-widest block mb-2">
                Şifre
              </label>
              <PasswordInput
                name="password"
                placeholder="••••••••"
                required
                disabled={loading || success}
                autoComplete="new-password"
              />
            </div>

            <button
              type="submit" disabled={loading || success}
              className="btn-primary w-full flex items-center justify-center gap-2
                rounded-xl py-3.5 mt-2 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? (
                <><Loader2 className="w-4 h-4 animate-spin" /> Oluşturuluyor…</>
              ) : (
                <><span>Hesap Oluştur</span><ArrowRight className="w-4 h-4" /></>
              )}
            </button>
          </form>

          <div className="border-t border-white/[0.06] my-7" />

          <p className="text-muted text-sm text-center">
            Zaten hesabın var mı?{" "}
            <Link href="/login" className="text-neon hover:text-neon/80 font-semibold transition-colors">
              Giriş Yap →
            </Link>
          </p>
        </motion.div>
      </div>
    </div>
  );
}
