"use client";

import React, { Suspense, useEffect, useRef, useState } from "react";
import { Loader2, AlertCircle } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { googleSignIn, saveAuthTokens } from "@/lib/api";
import { consumeGoogleOAuthState, googleCallbackRedirectUri } from "@/lib/googleAuth";

/**
 * Kullanıcının Google'ın rıza ekranında "İptal"e basması normal, beklenen
 * bir eylemdir — gerçek bir hata DEĞİLDİR. Diğer fırlatılan hatalardan
 * (CSRF state uyuşmazlığı, sunucu hatası) AYIRT etmek için ayrı bir sınıf
 * — `catch` bloğu bunu görürse alarm verici kırmızı hata kutusu yerine
 * nötr bir mesaj gösterir (M38 audit bulgusu: önceden ikisi de AYNI
 * `bg-destructive`/`AlertCircle` görsel diliyle gösteriliyordu).
 */
class GoogleCancelledError extends Error {}

function GoogleCallback() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [error, setError] = useState("");
  const [cancelled, setCancelled] = useState(false);
  // StrictMode/re-render'da tek kullanımlık `code`in İKİNCİ kez core-api'ye
  // gönderilmesini önler (Google authorization code'ları tek kullanımlıktır).
  const exchanged = useRef(false);

  useEffect(() => {
    if (exchanged.current) return;
    exchanged.current = true;

    // Senkron doğrulama hatalarını da async akışa taşır (throw → catch) —
    // setState'in effect gövdesi içinde DOĞRUDAN değil, her zaman bir
    // callback İÇİNDEN çağrılması için (react-hooks/set-state-in-effect).
    const run = async () => {
      const oauthError = searchParams.get("error");
      if (oauthError) {
        throw new GoogleCancelledError("Google girişi iptal edildi veya reddedildi.");
      }

      const code = searchParams.get("code");
      const state = searchParams.get("state");
      const next = consumeGoogleOAuthState(state);
      if (!code || !next) {
        throw new Error("Güvenlik doğrulaması başarısız oldu. Lütfen tekrar deneyin.");
      }

      const data = await googleSignIn(code, googleCallbackRedirectUri());
      saveAuthTokens(data);
      router.push(next);
    };

    run().catch((err: unknown) => {
      if (err instanceof GoogleCancelledError) {
        setCancelled(true);
        return;
      }
      setError(err instanceof Error ? err.message : "Google ile giriş başarısız oldu.");
    });
  }, [searchParams, router]);

  return (
    <div className="min-h-screen bg-bg flex items-center justify-center px-6">
      <div className="w-full max-w-md text-center">
        {cancelled ? (
          <div className="bg-surface border border-border rounded-lg p-8">
            <p className="text-text-secondary text-sm mb-6">Google girişi iptal edildi.</p>
            <Link href="/login" className="text-accent-text hover:opacity-80 font-semibold text-sm transition-opacity">
              Giriş sayfasına dön →
            </Link>
          </div>
        ) : error ? (
          <div className="bg-surface border border-border rounded-lg p-8">
            <div className="flex items-start gap-3 bg-destructive/10 border border-destructive/25
              text-destructive px-4 py-3.5 rounded-md mb-6 text-sm text-left" role="alert" aria-live="assertive">
              <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
              <span>{error}</span>
            </div>
            <Link href="/login" className="text-accent-text hover:opacity-80 font-semibold text-sm transition-opacity">
              Giriş sayfasına dön →
            </Link>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-3 text-text-secondary">
            <Loader2 className="w-6 h-6 animate-spin" />
            <p className="text-sm">Google ile giriş yapılıyor…</p>
          </div>
        )}
      </div>
    </div>
  );
}

export default function GoogleCallbackPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-bg" />}>
      <GoogleCallback />
    </Suspense>
  );
}
