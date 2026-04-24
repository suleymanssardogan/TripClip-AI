"use client";

import React, { useState } from "react";
import { motion } from "framer-motion";
import { Loader2, AlertCircle, CheckCircle, ArrowRight } from "lucide-react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { login } from "@/lib/api";

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
      localStorage.setItem("token",   data.access_token);
      localStorage.setItem("user_id", String(data.user_id));
      localStorage.setItem("email",   data.email);
      setSuccess(true);
      setTimeout(() => router.push("/dashboard"), 800);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "E-posta veya şifre hatalı.");
    } finally { setLoading(false); }
  };

  return (
    <div className="light-page min-h-screen flex">

      {/* ── Sol editorial panel ────────────────────────────── */}
      <div className="hidden lg:flex flex-col justify-between w-[480px] flex-shrink-0
        px-16 py-14 border-r border-warm-border"
        style={{ background: "#F2EDE3" }}>

        {/* Logo */}
        <Link href="/">
          <div>
            <p className="font-serif font-black text-charcoal text-2xl tracking-tight">TripClip</p>
            <p className="text-[9px] font-semibold tracking-[0.25em] uppercase text-gold mt-0">
              AI Travel
            </p>
          </div>
        </Link>

        {/* Büyük editorial metin */}
        <div>
          <span className="gold-line mb-8" />
          <h2 className="font-serif font-black text-charcoal leading-[1.05]"
            style={{ fontSize: "clamp(2.5rem, 4vw, 4rem)" }}>
            Seyahatini<br />
            yeniden<br />
            <em className="italic" style={{ color: "#C8A96E" }}>keşfet.</em>
          </h2>
          <p className="text-charcoal-mid text-sm leading-relaxed mt-6 max-w-xs">
            AI destekli gezi analizi ile videolarındaki her anı haritaya dönüştür,
            optimize edilmiş rotalar keşfet.
          </p>

          {/* Mini istatistik */}
          <div className="flex gap-8 mt-12 pt-8 border-t border-warm-border">
            {[
              { val: "∞", label: "Video Analizi" },
              { val: "100%", label: "Ücretsiz" },
            ].map((s, i) => (
              <div key={i}>
                <p className="font-serif font-black text-charcoal text-2xl">{s.val}</p>
                <p className="luxury-label mt-1">{s.label}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Alt */}
        <p className="text-charcoal-lt text-xs tracking-wider">
          Fırat Üniversitesi · 2026
        </p>
      </div>

      {/* ── Sağ form ──────────────────────────────────────── */}
      <div className="flex-1 flex items-center justify-center px-8 py-16 bg-cream">
        <motion.div
          initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, ease: "easeOut" }}
          className="w-full max-w-sm"
        >
          {/* Mobil logo */}
          <Link href="/" className="flex flex-col mb-12 lg:hidden">
            <p className="font-serif font-black text-charcoal text-2xl">TripClip</p>
            <p className="text-[9px] font-semibold tracking-[0.25em] uppercase text-gold">AI Travel</p>
          </Link>

          <div className="mb-10">
            <span className="luxury-label">Hoş Geldin</span>
            <h1 className="font-serif font-black text-charcoal text-4xl mt-2 leading-tight">
              Giriş Yap
            </h1>
          </div>

          {/* Hata */}
          {error && (
            <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }}
              className="flex items-start gap-3 border border-red-200 bg-red-50 text-red-700
                px-4 py-3.5 mb-6 text-sm">
              <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
              <span>{error}</span>
            </motion.div>
          )}

          {/* Başarı */}
          {success && (
            <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }}
              className="flex items-center gap-3 border border-green-200 bg-green-50 text-green-700
                px-4 py-3.5 mb-6 text-sm">
              <CheckCircle className="w-4 h-4 flex-shrink-0" />
              <span>Giriş başarılı, yönlendiriliyorsunuz…</span>
            </motion.div>
          )}

          <form onSubmit={handleLogin} className="space-y-5">
            <div>
              <label className="luxury-label block mb-2">E-posta</label>
              <input name="email" type="email" placeholder="sen@ornek.com"
                className="w-full bg-white border border-warm-border px-4 py-3.5
                  text-charcoal placeholder:text-charcoal-lt text-sm
                  focus:outline-none focus:border-charcoal transition-colors"
                required disabled={loading || success} />
            </div>
            <div>
              <label className="luxury-label block mb-2">Şifre</label>
              <input name="password" type="password" placeholder="••••••••"
                className="w-full bg-white border border-warm-border px-4 py-3.5
                  text-charcoal placeholder:text-charcoal-lt text-sm
                  focus:outline-none focus:border-charcoal transition-colors"
                required disabled={loading || success} />
            </div>

            <button type="submit" disabled={loading || success}
              className="luxury-btn w-full justify-center mt-2 disabled:opacity-50">
              {loading ? (
                <><Loader2 className="w-4 h-4 animate-spin" /> Giriş yapılıyor…</>
              ) : (
                <><span>Giriş Yap</span><ArrowRight className="w-4 h-4" /></>
              )}
            </button>
          </form>

          <hr className="luxury-divider my-8" />

          <p className="text-charcoal-mid text-sm text-center">
            Hesabın yok mu?{" "}
            <Link href="/signup" className="luxury-link inline-flex">
              Kaydol <ArrowRight className="w-3 h-3" />
            </Link>
          </p>
        </motion.div>
      </div>
    </div>
  );
}
