"use client";

import React, { useState } from "react";
import { motion } from "framer-motion";
import { Loader2, CheckCircle, ArrowRight } from "lucide-react";
import Link from "next/link";
import { forgotPassword } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";

export default function ForgotPasswordPage() {
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (loading) return;
    setLoading(true);
    const fd = new FormData(e.currentTarget);
    try {
      // Backend hesap var/yok fark etmeksizin AYNI yanıtı döner (kullanıcı
      // numaralandırmayı önlemek için) — bu yüzden burada da hata dalı YOK,
      // ağ hatası dışında her zaman başarı gösterilir.
      await forgotPassword(fd.get("email") as string);
    } catch {
      // Ağ hatası bile olsa aynı genel mesaj gösterilir — bir hesabın var
      // olup olmadığını farklı davranışla İMA ETMEMEK için.
    } finally {
      setLoading(false);
      setSuccess(true);
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
            <h1 className="font-display font-black text-text text-3xl">Şifremi Unuttum</h1>
          </div>

          {success ? (
            <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }}
              className="flex items-start gap-3 bg-success/10 border border-success/25
                text-success px-4 py-3.5 rounded-md text-sm">
              <CheckCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
              <span>Bu e-posta adresine kayıtlı bir hesap varsa, şifre sıfırlama linki gönderildi. Gelen kutunuzu kontrol edin.</span>
            </motion.div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-5">
              <p className="text-text-secondary text-sm">
                Hesabınıza kayıtlı e-posta adresini girin, size bir şifre sıfırlama linki gönderelim.
              </p>
              <div>
                <label htmlFor="email" className="font-mono text-xs text-text-tertiary uppercase tracking-widest block mb-2">
                  E-posta
                </label>
                <Input
                  id="email" name="email" type="email" placeholder="sen@ornek.com"
                  required disabled={loading}
                />
              </div>

              <Button type="submit" disabled={loading} className="w-full py-3.5 mt-2">
                {loading ? (
                  <><Loader2 className="w-4 h-4 animate-spin" /> Gönderiliyor…</>
                ) : (
                  <><span>Sıfırlama Linki Gönder</span><ArrowRight className="w-4 h-4" /></>
                )}
              </Button>
            </form>
          )}

          <div className="border-t border-border my-7" />

          <p className="text-text-secondary text-sm text-center">
            <Link href="/login" className="text-accent-text hover:opacity-80 font-semibold transition-opacity">
              ← Giriş sayfasına dön
            </Link>
          </p>
        </motion.div>
      </div>
    </div>
  );
}
