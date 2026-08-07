"use client";

import React, { useEffect, useState } from "react";
import { motion } from "framer-motion";
import {
  Loader2, AlertCircle, CheckCircle2, XCircle, Users, MapPin, Smartphone,
} from "lucide-react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import Navbar from "@/components/Navbar";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { getSharePreview, acceptShare, declineShare, type SharePreview } from "@/lib/api";

const ROLE_LABELS: Record<string, string> = {
  viewer: "Görüntüleyici",
  editor: "Düzenleyici",
};

type Outcome = "accepted" | "declined" | null;

export default function InvitePage() {
  const params = useParams();
  const router = useRouter();
  const token = String(params.token);

  const [preview, setPreview] = useState<SharePreview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState("");
  const [submitting, setSubmitting] = useState<"accept" | "decline" | null>(null);
  const [outcome, setOutcome] = useState<Outcome>(null);
  const [loggedIn, setLoggedIn] = useState(false);

  useEffect(() => {
    setTimeout(() => setLoggedIn(!!localStorage.getItem("token")), 0);
    getSharePreview(token)
      .then(res => {
        setTimeout(() => {
          setPreview(res);
          setLoading(false);
        }, 0);
      })
      .catch(e => {
        setTimeout(() => {
          setError(e.message);
          setLoading(false);
        }, 0);
      });
  }, [token]);

  async function handleAccept() {
    setSubmitting("accept"); setError("");
    try {
      // Trip Builder gezileri (bu davetlerin konusu) şu an yalnızca iOS'ta
      // görüntülenebiliyor — web'de bir /trips/[id] görüntüleyici yok, bu
      // yüzden kabul sonrası bir sayfaya yönlendirmek yerine "uygulamayı aç"
      // yönlendirmesiyle bitiriyoruz (bkz. web-bff/app/routes/trip_sharing.py).
      await acceptShare(token);
      setOutcome("accepted");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Davet kabul edilemedi.");
    } finally { setSubmitting(null); }
  }

  async function handleDecline() {
    setSubmitting("decline"); setError("");
    try {
      await declineShare(token);
      setOutcome("declined");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Davet reddedilemedi.");
    } finally { setSubmitting(null); }
  }

  /* ─── States ─── */

  if (loading) {
    return (
      <div className="min-h-screen bg-bg flex items-center justify-center">
        <Loader2 className="w-8 h-8 text-accent-text animate-spin" />
      </div>
    );
  }

  if (error && !preview) {
    return (
      <div className="min-h-screen bg-bg font-sans text-text">
        <Navbar />
        <main className="max-w-md mx-auto px-6 pt-40 flex flex-col items-center text-center gap-4">
          <div className="w-14 h-14 rounded-full bg-destructive/10 border border-destructive/25 flex items-center justify-center">
            <AlertCircle className="w-6 h-6 text-destructive" />
          </div>
          <h1 className="font-display font-black text-2xl text-text">Davet Geçersiz</h1>
          <p className="text-text-tertiary text-sm">{error}</p>
          <Link href="/" className="text-accent-text hover:underline text-sm font-semibold mt-2">
            Ana Sayfaya Dön
          </Link>
        </main>
      </div>
    );
  }

  if (outcome === "accepted") {
    return (
      <div className="min-h-screen bg-bg font-sans text-text">
        <Navbar />
        <main className="max-w-md mx-auto px-6 pt-40 flex flex-col items-center text-center gap-4">
          <div className="w-14 h-14 rounded-full bg-success/10 border border-success/25 flex items-center justify-center">
            <CheckCircle2 className="w-6 h-6 text-success" />
          </div>
          <h1 className="font-display font-black text-2xl text-text">Katıldın!</h1>
          <p className="text-text-tertiary text-sm">
            Geziyi görüntülemek ve düzenlemek için TripClip mobil uygulamasını aç.
          </p>
          <Link href="/dashboard" className="text-accent-text hover:underline text-sm font-semibold mt-2">
            Dashboard&apos;a Dön
          </Link>
        </main>
      </div>
    );
  }

  if (outcome === "declined") {
    return (
      <div className="min-h-screen bg-bg font-sans text-text">
        <Navbar />
        <main className="max-w-md mx-auto px-6 pt-40 flex flex-col items-center text-center gap-4">
          <div className="w-14 h-14 rounded-full bg-surface2 border border-border flex items-center justify-center">
            <XCircle className="w-6 h-6 text-text-tertiary" />
          </div>
          <h1 className="font-display font-black text-2xl text-text">Davet Reddedildi</h1>
          <p className="text-text-tertiary text-sm">Bu daveti reddettin.</p>
          <Link href="/" className="text-accent-text hover:underline text-sm font-semibold mt-2">
            Ana Sayfaya Dön
          </Link>
        </main>
      </div>
    );
  }

  const roleLabel = preview ? (ROLE_LABELS[preview.role] ?? preview.role) : "";

  return (
    <div className="min-h-screen bg-bg font-sans text-text">
      <Navbar />
      <main className="max-w-md mx-auto px-6 pt-32 pb-20">
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
          <Card className="p-8">
            <div className="flex items-center gap-3 mb-6">
              <div className="w-11 h-11 rounded-md bg-accent/10 border border-accent/20 flex items-center justify-center text-accent-text shrink-0">
                <Users className="w-5 h-5" />
              </div>
              <div>
                <p className="font-mono text-[10px] text-text-tertiary uppercase tracking-widest">Gezi Daveti</p>
                <h1 className="font-display font-black text-xl text-text tracking-tight">{preview?.trip_title}</h1>
              </div>
            </div>

            <div className="flex items-center gap-6 mb-6 text-sm">
              <div className="flex items-center gap-2 text-text-secondary">
                <MapPin className="w-4 h-4 text-route" />
                <span>{preview?.stops_count} durak</span>
              </div>
              <div className="flex items-center gap-2 text-text-secondary">
                <Users className="w-4 h-4 text-accent-text" />
                <span>{roleLabel} olarak</span>
              </div>
            </div>

            {error && (
              <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }}
                className="flex items-start gap-3 bg-destructive/10 border border-destructive/25
                  text-destructive px-4 py-3.5 rounded-md mb-6 text-sm"
                role="alert" aria-live="assertive">
                <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
                <span>{error}</span>
              </motion.div>
            )}

            {loggedIn ? (
              <div className="flex gap-3">
                <Button
                  onClick={handleAccept}
                  disabled={submitting !== null}
                  className="flex-1 py-3.5"
                >
                  {submitting === "accept" ? <Loader2 className="w-4 h-4 animate-spin" /> : "Kabul Et"}
                </Button>
                <Button
                  variant="outline" onClick={handleDecline}
                  disabled={submitting !== null}
                  className="flex-1 py-3.5"
                >
                  {submitting === "decline" ? <Loader2 className="w-4 h-4 animate-spin" /> : "Reddet"}
                </Button>
              </div>
            ) : (
              <div className="space-y-3">
                <p className="text-text-tertiary text-xs text-center">
                  Bu daveti kabul etmek için giriş yapman gerekiyor.
                </p>
                <Button
                  onClick={() => router.push(`/login?next=${encodeURIComponent(`/invite/${token}`)}`)}
                  className="w-full py-3.5"
                >
                  Giriş Yap
                </Button>
                <Button
                  variant="outline"
                  onClick={() => router.push(`/signup?next=${encodeURIComponent(`/invite/${token}`)}`)}
                  className="w-full py-3.5"
                >
                  Hesap Oluştur
                </Button>
              </div>
            )}
          </Card>

          <div className="flex items-center gap-2 justify-center mt-6 text-text-tertiary text-xs">
            <Smartphone className="w-3.5 h-3.5" />
            <span>Gezinin tamamını görüntülemek için TripClip mobil uygulamasını kullan.</span>
          </div>
        </motion.div>
      </main>
    </div>
  );
}
