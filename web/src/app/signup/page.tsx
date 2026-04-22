"use client";

import React, { useState } from "react";
import Navbar from "@/components/Navbar";
import { UserPlus, Loader2, AlertCircle, CheckCircle } from "lucide-react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { register } from "@/lib/api";

export default function SignupPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);

  const handleSignup = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setLoading(true);
    setError("");

    const formData = new FormData(e.currentTarget);
    const email = formData.get("email") as string;
    const password = formData.get("password") as string;
    const username = formData.get("username") as string;

    try {
      const data = await register(email, password, username);
      localStorage.setItem("token", data.access_token);
      localStorage.setItem("user_id", String(data.user_id));
      localStorage.setItem("email", email);
      setSuccess(true);
      setTimeout(() => router.push("/welcome"), 1000);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Kayıt sırasında bir hata oluştu.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-bg pt-24 px-6 flex items-center justify-center">
      <Navbar />

      {/* Background orbs */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden">
        <div className="orb w-96 h-96 bg-neon top-1/4 -left-48" />
        <div className="orb w-80 h-80 bg-violet bottom-1/4 -right-40" />
      </div>

      <div className="relative w-full max-w-md">
        {/* Card */}
        <div className="glass rounded-2xl p-8 border border-white/8">
          {/* Logo mark */}
          <div className="flex flex-col items-center mb-8">
            <div className="w-14 h-14 bg-neon/10 border border-neon/20 rounded-2xl flex items-center justify-center mb-4">
              <UserPlus className="w-7 h-7 text-neon" />
            </div>
            <h1 className="font-display font-black text-2xl text-ice">Hesap Oluştur</h1>
            <p className="text-muted text-sm mt-1">Seyahat rotalarını keşfetmeye başla</p>
          </div>

          {/* Error */}
          {error && (
            <div className="bg-coral/10 border border-coral/20 text-coral p-3.5 rounded-xl mb-5 text-sm flex items-center gap-2">
              <AlertCircle className="w-4 h-4 flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {/* Success */}
          {success && (
            <div className="bg-neon/10 border border-neon/20 text-neon p-3.5 rounded-xl mb-5 text-sm flex items-center gap-2">
              <CheckCircle className="w-4 h-4 flex-shrink-0" />
              <span>Hesap oluşturuldu! Yönlendiriliyorsunuz...</span>
            </div>
          )}

          <form onSubmit={handleSignup} className="space-y-4">
            <div>
              <label className="text-xs text-muted font-medium mb-1.5 block">Kullanıcı Adı</label>
              <input
                name="username"
                type="text"
                placeholder="tripclip_user"
                className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-ice placeholder:text-muted/50 text-sm focus:outline-none focus:border-neon/40 focus:bg-neon/5 transition-all"
                required
                disabled={loading || success}
              />
            </div>
            <div>
              <label className="text-xs text-muted font-medium mb-1.5 block">E-posta</label>
              <input
                name="email"
                type="email"
                placeholder="sen@ornek.com"
                className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-ice placeholder:text-muted/50 text-sm focus:outline-none focus:border-neon/40 focus:bg-neon/5 transition-all"
                required
                disabled={loading || success}
              />
            </div>
            <div>
              <label className="text-xs text-muted font-medium mb-1.5 block">Şifre</label>
              <input
                name="password"
                type="password"
                placeholder="••••••••"
                className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-ice placeholder:text-muted/50 text-sm focus:outline-none focus:border-neon/40 focus:bg-neon/5 transition-all"
                required
                disabled={loading || success}
              />
            </div>

            <button
              type="submit"
              disabled={loading || success}
              className="w-full btn-primary py-3.5 rounded-xl font-bold text-sm tracking-wide flex items-center justify-center gap-2 mt-2 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? (
                <><Loader2 className="w-4 h-4 animate-spin" /> Oluşturuluyor...</>
              ) : (
                "Hesap Oluştur"
              )}
            </button>
          </form>

          <p className="mt-6 text-center text-sm text-muted">
            Zaten hesabın var mı?{" "}
            <Link href="/login" className="text-neon hover:text-neon/80 transition-colors font-medium">
              Giriş Yap
            </Link>
          </p>
        </div>

        {/* Footer note */}
        <p className="text-center text-xs text-muted/40 mt-4">
          Kaydolarak kullanım koşullarını kabul etmiş olursunuz.
        </p>
      </div>
    </div>
  );
}
