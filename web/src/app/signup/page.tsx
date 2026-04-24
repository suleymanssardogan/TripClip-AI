"use client";

import React, { useState } from "react";
import { motion } from "framer-motion";
import { Loader2, AlertCircle, CheckCircle, ArrowRight } from "lucide-react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { register } from "@/lib/api";

const BENEFITS = [
  "Sonsuz video analizi",
  "Otomatik lokasyon tespiti",
  "Optimize edilmiş rota planı",
  "Türkçe ses tanıma desteği",
];

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
    <div className="light-page min-h-screen flex">

      {/* ── Sol panel ────────────────────────────────────────── */}
      <div className="hidden lg:flex flex-col justify-between w-[480px] flex-shrink-0
        px-16 py-14 border-r border-warm-border"
        style={{ background: "#F2EDE3" }}>

        <Link href="/">
          <div>
            <p className="font-serif font-black text-charcoal text-2xl">TripClip</p>
            <p className="text-[9px] font-semibold tracking-[0.25em] uppercase text-gold">AI Travel</p>
          </div>
        </Link>

        <div>
          <span className="gold-line mb-8" />
          <h2 className="font-serif font-black text-charcoal leading-[1.05]"
            style={{ fontSize: "clamp(2.5rem, 4vw, 4rem)" }}>
            Seyahat<br />
            <em className="italic" style={{ color: "#C8A96E" }}>asistanın.</em>
          </h2>
          <p className="text-charcoal-mid text-sm leading-relaxed mt-6 max-w-xs">
            Ücretsiz hesap oluştur. Gezi videolarını yükle,
            yapay zeka otomatik olarak seyahat planını hazırlasın.
          </p>

          <ul className="mt-10 space-y-4">
            {BENEFITS.map((b, i) => (
              <li key={i} className="flex items-center gap-3 text-sm text-charcoal-mid">
                <span className="gold-line !w-3 flex-shrink-0" />
                {b}
              </li>
            ))}
          </ul>
        </div>

        <p className="text-charcoal-lt text-xs tracking-wider">Fırat Üniversitesi · 2026</p>
      </div>

      {/* ── Sağ form ──────────────────────────────────────────── */}
      <div className="flex-1 flex items-center justify-center px-8 py-16 bg-cream">
        <motion.div
          initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, ease: "easeOut" }}
          className="w-full max-w-sm"
        >
          <Link href="/" className="flex flex-col mb-12 lg:hidden">
            <p className="font-serif font-black text-charcoal text-2xl">TripClip</p>
            <p className="text-[9px] font-semibold tracking-[0.25em] uppercase text-gold">AI Travel</p>
          </Link>

          <div className="mb-10">
            <span className="luxury-label">Başla</span>
            <h1 className="font-serif font-black text-charcoal text-4xl mt-2 leading-tight">
              Hesap Oluştur
            </h1>
          </div>

          {error && (
            <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }}
              className="flex items-start gap-3 border border-red-200 bg-red-50 text-red-700
                px-4 py-3.5 mb-6 text-sm">
              <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
              <span>{error}</span>
            </motion.div>
          )}

          {success && (
            <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }}
              className="flex items-center gap-3 border border-green-200 bg-green-50 text-green-700
                px-4 py-3.5 mb-6 text-sm">
              <CheckCircle className="w-4 h-4 flex-shrink-0" />
              <span>Hesap oluşturuldu! Yönlendiriliyorsunuz…</span>
            </motion.div>
          )}

          <form onSubmit={handleSignup} className="space-y-5">
            {[
              { name: "username", label: "Kullanıcı Adı", type: "text",     ph: "gezgin_ali" },
              { name: "email",    label: "E-posta",        type: "email",    ph: "sen@ornek.com" },
              { name: "password", label: "Şifre",          type: "password", ph: "••••••••" },
            ].map(field => (
              <div key={field.name}>
                <label className="luxury-label block mb-2">{field.label}</label>
                <input
                  name={field.name} type={field.type} placeholder={field.ph}
                  className="w-full bg-white border border-warm-border px-4 py-3.5
                    text-charcoal placeholder:text-charcoal-lt text-sm
                    focus:outline-none focus:border-charcoal transition-colors"
                  required disabled={loading || success}
                />
              </div>
            ))}

            <button type="submit" disabled={loading || success}
              className="luxury-btn w-full justify-center mt-2 disabled:opacity-50">
              {loading ? (
                <><Loader2 className="w-4 h-4 animate-spin" /> Oluşturuluyor…</>
              ) : (
                <><span>Hesap Oluştur</span><ArrowRight className="w-4 h-4" /></>
              )}
            </button>
          </form>

          <hr className="luxury-divider my-8" />

          <p className="text-charcoal-mid text-sm text-center">
            Zaten hesabın var mı?{" "}
            <Link href="/login" className="luxury-link inline-flex">
              Giriş Yap <ArrowRight className="w-3 h-3" />
            </Link>
          </p>
        </motion.div>
      </div>
    </div>
  );
}
