"use client";

import { Button } from "@/components/ui/Button";
import { isGoogleSignInConfigured, redirectToGoogleSignIn } from "@/lib/googleAuth";

interface Props {
  next: string;
  disabled?: boolean;
}

/**
 * `NEXT_PUBLIC_GOOGLE_CLIENT_ID` set edilmemişse hiçbir şey render etmez —
 * yarım/çalışmayan bir buton göstermek yerine sessizce gizlenir (backend'in
 * `is_configured` deseniyle aynı "optional infra degrades gracefully"
 * felsefesi, bkz. googleAuth.ts).
 */
export default function GoogleSignInButton({ next, disabled }: Props) {
  if (!isGoogleSignInConfigured()) return null;

  return (
    <div>
      <div className="flex items-center gap-3 my-6">
        <div className="h-px flex-1 bg-border" />
        <span className="font-mono text-[10px] text-text-tertiary uppercase tracking-widest">veya</span>
        <div className="h-px flex-1 bg-border" />
      </div>
      <Button
        type="button"
        variant="outline"
        className="w-full py-3.5"
        disabled={disabled}
        onClick={() => redirectToGoogleSignIn(next)}
      >
        <svg viewBox="0 0 48 48" className="w-4 h-4" aria-hidden="true">
          <path fill="#FFC107" d="M43.6 20.5H42V20H24v8h11.3c-1.6 4.7-6.1 8-11.3 8-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.9 1.2 8 3.1l5.7-5.7C34.6 6.1 29.6 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.7-.4-3.5z"/>
          <path fill="#FF3D00" d="M6.3 14.7l6.6 4.8C14.6 15.9 18.9 13 24 13c3.1 0 5.9 1.2 8 3.1l5.7-5.7C34.6 6.1 29.6 4 24 4 16.3 4 9.7 8.3 6.3 14.7z"/>
          <path fill="#4CAF50" d="M24 44c5.5 0 10.5-2.1 14.3-5.5l-6.6-5.6C29.6 34.7 26.9 36 24 36c-5.2 0-9.6-3.3-11.2-8l-6.6 5.1C9.5 39.6 16.2 44 24 44z"/>
          <path fill="#1976D2" d="M43.6 20.5H42V20H24v8h11.3c-.8 2.3-2.2 4.2-4.1 5.6l6.6 5.6C41.9 35.9 44 30.4 44 24c0-1.3-.1-2.7-.4-3.5z"/>
        </svg>
        <span>Google ile devam et</span>
      </Button>
    </div>
  );
}
