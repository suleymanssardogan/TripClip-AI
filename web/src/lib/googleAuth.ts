/**
 * Google Sign-In (OAuth 2.0 Authorization Code flow) — web istemcisi tarafı.
 *
 * Yalnızca genel `client_id`i taşır; `client_secret` HİÇBİR ZAMAN buraya
 * gelmez — kod→token değişimi yalnızca core-api'de (confidential client
 * olarak) yapılır (bkz. AuthService._exchange_and_verify_google_code).
 * `NEXT_PUBLIC_GOOGLE_CLIENT_ID` set edilmemişse Google girişi devre dışı
 * kalır — backend'deki "optional infra degrades gracefully" deseniyle
 * tutarlı (bkz. EmailService.is_configured, ApnsClient.is_configured).
 */

const GOOGLE_AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth";
const STATE_STORAGE_KEY = "tripclip_google_oauth_state";
const NEXT_STORAGE_KEY = "tripclip_google_oauth_next";

export function isGoogleSignInConfigured(): boolean {
  return Boolean(process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID);
}

export function googleCallbackRedirectUri(): string {
  return `${window.location.origin}/auth/google/callback`;
}

/**
 * Kullanıcıyı Google'ın rıza ekranına yönlendirir. `next`, geri dönüşte
 * (callback sayfasında) hangi sayfaya yönlendirileceğini taşır — Google'ın
 * kendi `state` parametresi CSRF koruması için ayrıca kullanılır (rastgele
 * bir nonce, sessionStorage'da saklanıp callback'te doğrulanır).
 */
export function redirectToGoogleSignIn(next: string): void {
  const clientId = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID;
  if (!clientId) return;

  const state = crypto.randomUUID();
  sessionStorage.setItem(STATE_STORAGE_KEY, state);
  sessionStorage.setItem(NEXT_STORAGE_KEY, next);

  const params = new URLSearchParams({
    client_id: clientId,
    redirect_uri: googleCallbackRedirectUri(),
    response_type: "code",
    scope: "openid email profile",
    state,
    prompt: "select_account",
  });
  window.location.href = `${GOOGLE_AUTH_ENDPOINT}?${params.toString()}`;
}

/**
 * Callback sayfasında çağrılır — `state`in redirect öncesi saklananla
 * eşleştiğini doğrular (CSRF koruması) ve saklanan `next` yolunu döner.
 * Eşleşmezse (veya hiç başlatılmamışsa) null döner — çağıran bunu
 * güvenli bir hata olarak ele almalı, sessizce devam ETMEMELİ.
 */
export function consumeGoogleOAuthState(receivedState: string | null): string | null {
  const expected = sessionStorage.getItem(STATE_STORAGE_KEY);
  const next = sessionStorage.getItem(NEXT_STORAGE_KEY);
  sessionStorage.removeItem(STATE_STORAGE_KEY);
  sessionStorage.removeItem(NEXT_STORAGE_KEY);

  if (!expected || !receivedState || receivedState !== expected) return null;
  return next && next.startsWith("/") && !next.startsWith("//") ? next : "/dashboard";
}
