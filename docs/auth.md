# Authentication, Account Recovery & Google Sign-In (Milestone 34)

Extends the existing email/password + Sign in with Apple auth system with
password reset and Google Sign-In, and fixes concrete cross-platform UX/
consistency gaps found during audit. **No new architecture** — every
addition mirrors an existing, already-proven pattern in this codebase.

## Why this design

Before writing any code, the existing auth stack was inspected:

- `services/core-api/app/core/auth.py` — bcrypt password hashing,
  JWT (HS256) access tokens, and *generic* `generate_secure_token()`/
  `hash_token()` helpers (`secrets.token_urlsafe` + SHA-256) already used
  for refresh tokens and share-invite tokens.
- `app/models/refresh_token.py` / `share_token.py` — the existing
  pattern for opaque, DB-backed, single-use, hash-stored tokens.
- `app/infrastructure/repositories/sql_refresh_token_repository.py`'s
  `revoke_if_active` — an atomic `UPDATE ... WHERE x IS NULL` + rowcount
  check, making single-use token consumption race-safe without a
  read-then-write race.
- `AuthService.apple_sign_in()` / `_verify_apple_token()` — the existing
  external-identity-provider template (JWKS fetch, signature
  verification, account lookup/creation).
- `ApnsClient.is_configured` — the established "optional infrastructure
  degrades gracefully" pattern (push notifications silently no-op if
  APNs credentials aren't set).

Given this, password reset reuses the *exact* refresh-token pattern
(new `PasswordResetToken` model, same atomic-claim repository shape) and
Google Sign-In reuses the *exact* Apple Sign-In pattern (JWKS-based
verification, same account-linking decision tree), rather than inventing
new token or identity-provider abstractions.

## Password Reset

### Token lifecycle

1. `POST /internal/auth/forgot-password {email}` → `AuthService.request_password_reset()`:
   - Looks up the user by email. **Regardless of whether the account
     exists**, the HTTP response is identical (`{"status": "ok"}`,
     200) — this prevents user enumeration via response
     content, status code, or timing (the DB lookup happens either way).
   - If the account exists, any *previous* unused reset tokens for that
     user are invalidated (`invalidate_all_for_user`) before a new one is
     issued — at most one live reset token per user.
   - A new token is generated via the existing generic
     `generate_secure_token()` (32 bytes, URL-safe) — **only the SHA-256
     hash** (`hash_token()`) is stored in `password_reset_tokens.token_hash`
     (unique-indexed); the raw token is never persisted anywhere.
   - The raw token is embedded in a reset URL
     (`PASSWORD_RESET_URL_BASE` + `?token=...`, default
     `http://localhost:3000/reset-password`) and emailed via `EmailService`.
     The raw token is **never logged** — only send success/failure and
     the exception type name are logged.
   - Expiry: `PASSWORD_RESET_TOKEN_EXPIRE_MINUTES` (default 30).

2. `POST /internal/auth/reset-password {token, new_password}` → `AuthService.reset_password()`:
   - The raw token is hashed and looked up by `token_hash`.
   - Three distinct, specific failure codes (mirroring the refresh-token
     reuse-detection pattern): `PASSWORD_RESET_TOKEN_INVALID` (no such
     hash), `PASSWORD_RESET_TOKEN_USED`, `PASSWORD_RESET_TOKEN_EXPIRED`.
   - Consumption is atomic: `mark_used_if_active()` does a single
     `UPDATE ... WHERE id = :id AND used_at IS NULL` and checks rowcount
     — two concurrent requests with the same valid token can never both
     succeed.
   - On success, the password is updated (same bcrypt hashing, same
     `_validate_password_strength()` rule as registration — extracted to
     a shared module-level function so the two call sites can never
     drift) and **all of that user's own refresh tokens are revoked**
     (`revoke_all_for_user`) — this is the user's own sessions being
     force-logged-out after a credential change, not unrelated users or
     an unrelated session being touched.

### Email delivery

`app/infrastructure/email/email_service.py` — stdlib `smtplib`, no new
dependency. `EmailService.is_configured` (same shape as
`ApnsClient.is_configured`) checks `SMTP_HOST`/`SMTP_USER`/`SMTP_PASSWORD`;
if unset, `send()` is a no-op that returns `False`, and
`request_password_reset()` **deliberately ignores that return value** —
the anti-enumeration response is identical whether or not the email
actually sent, since a caller able to distinguish "email failed" from
"email sent" could use that to test whether a target email is registered
by triggering an SMTP-level bounce/rejection.

## Google Sign-In (OAuth 2.0 Authorization Code flow)

### Why Authorization Code, not implicit/PKCE-in-client

core-api acts as a **confidential OAuth client**: it holds
`GOOGLE_CLIENT_SECRET` server-side only and performs the code→token
exchange itself. Web and iOS only ever need the *public*
`GOOGLE_CLIENT_ID` to construct the authorization URL — this satisfies
"never expose client secrets to Web/iOS clients" without needing PKCE in
either client.

### Flow

1. Client (web or iOS) builds `https://accounts.google.com/o/oauth2/v2/auth`
   with `client_id`, `redirect_uri`, `scope=openid email profile`, and a
   random `state` (stored client-side, verified on return — CSRF
   protection independent of anything server-side).
2. Google redirects back to `redirect_uri` with `?code=...&state=...`.
3. Client calls `POST /internal/auth/google {code, redirect_uri}`.
4. `AuthService.google_sign_in()`:
   - `_validate_google_redirect_uri()` checks `redirect_uri` against the
     server-side allowlist `GOOGLE_ALLOWED_REDIRECT_URIS` (comma-separated)
     **before** any call to Google — an attacker-supplied `redirect_uri`
     is rejected early, not trusted.
   - `_exchange_and_verify_google_code()` does the actual code→token
     exchange (`POST https://oauth2.googleapis.com/token` with
     `client_id` + `client_secret`), then verifies the returned `id_token`'s
     signature against Google's JWKS — mirrors `_verify_apple_token()`'s
     structure. Issuer is checked against `("https://accounts.google.com",
     "accounts.google.com")` (Google's id_tokens use either form).
   - If `GOOGLE_CLIENT_ID`/`GOOGLE_CLIENT_SECRET` aren't configured, or
     the redirect URI isn't allowlisted, the endpoint fails safely with
     `GOOGLE_AUTH_UNAVAILABLE` (401) — no partial/undefined behavior.

### Account resolution (5 scenarios)

| Scenario | Behavior |
|---|---|
| Existing `google_id` match | Sign in to that account (Google's `sub` is the stable identity key — checked *before* email, so a user's email/name changing at Google doesn't break sign-in). |
| No `google_id` match, but email matches an existing account, **email_verified=true** | Link: set `google_id` on the existing account, sign in. Password login continues to work afterward — linking never disables the password path. |
| No `google_id` match, email matches an existing account, **email_verified=false** | **Reject** with `GOOGLE_EMAIL_NOT_VERIFIED` (401). Never silently merges into someone else's account on an unverified email, and never attempts to `create()` a duplicate-email row either (would crash on the unique constraint) — the existing account is left completely untouched. |
| No `google_id` match, no email match, any `email_verified` value | Create a new account. Verification is only required for *merging into an existing identity* — a brand-new identity has no merge risk, so it doesn't need a verified email to be created. |
| No email at all in the Google response | Rejected (`AuthException`, 400) — an account must have *some* identifying email. |

## BFF Error Code Registration (bug found & fixed during this milestone)

While registering the five new error codes
(`PASSWORD_RESET_TOKEN_INVALID/_EXPIRED/_USED`, `GOOGLE_AUTH_UNAVAILABLE`,
`GOOGLE_EMAIL_NOT_VERIFIED`) in both BFFs' `error_wrapper.py`, a
**pre-existing, unrelated bug** was found and fixed: `REFRESH_TOKEN_INVALID`,
`REFRESH_TOKEN_EXPIRED`, `REFRESH_TOKEN_REUSED`, and
`REFRESH_TOKEN_RACE_LOST` — all returned by core-api's `/internal/auth/refresh`
with HTTP 401 — were **not registered** in either
`mobile-bff/app/core/error_wrapper.py` or `web-bff/app/core/error_wrapper.py`.
Both BFFs derive their own outgoing status code purely from the `code`
string (independent of core-api's actual returned status), so an
unregistered code silently fell through to the default `400`.

Impact: a stolen or reused refresh token — or simply one that expired —
would reach the iOS client as HTTP 400, not 401. `APIClient.swift`'s
retry/force-logout path and `AuthEnvironment.handleUnauthorized()` are
both gated on `apiError.isUnauthorized`, which only becomes `true` for a
genuine 401. A 400 in this position would **not** force the client to
log out and re-authenticate — this is the same class of bug the project
has been warned about before (Milestone 26, "unregistered error codes
silently degrade to a generic status code"). Fixed by registering all
four codes into the 401 branch of both BFFs' status-mapping logic, with
regression tests (`test_refresh_token_error_codes_map_to_401`,
parametrized over all four codes) added to both `mobile-bff/tests/test_auth.py`
and `web-bff/tests/test_auth.py` so this cannot silently regress again.

## Cross-Platform UX Fixes

Found during the Section 6/7 cross-platform audit, fixed as part of this
milestone (each is either directly part of the new auth surface, or the
identical bug/inconsistency pattern the milestone explicitly asked to
find):

- **Web**: `src/lib/api.ts`'s 401→refresh-failed redirect to `/login`
  discarded the user's current page; it now appends `?next=<path>` so
  login returns them to where they were (the login/signup pages already
  supported reading `next`, they just never received it from this path).
- **Web**: login/signup forms had `<label>` elements with no `htmlFor`/`id`
  association; added throughout (login, signup, and the two new
  forgot/reset-password forms).
- **Web**: login/signup submit handlers relied only on the submit button's
  `disabled` state for re-entrancy; added an explicit `if (loading) return;`
  guard matching the established convention already used by every
  trip-mutation handler in the app (optimize, delete, undo, etc.).
- **iOS**: `HomeView`'s logout button fired immediately with no
  confirmation, inconsistent with plan deletion on the same screen
  (which already confirms). Added a `confirmationDialog`, mirroring the
  existing plan-deletion one exactly.
- **iOS**: per-stop delete (`LocationCard.EditActions.onDelete`) fired
  immediately with no confirmation in both `TripDetailView` and
  `ResultsView` (the same shared component, same bug, in both of its two
  usages), inconsistent with trip-level delete on the same screens
  (which already confirms). Added matching `confirmationDialog`s to both.

Two **pre-existing** cross-BFF asymmetries were found but deliberately
**not** touched, since they predate this milestone and neither intersects
the new auth work: `web-bff`'s `_WEB_MESSAGES` and `mobile-bff`'s
`_MOBILE_MESSAGES` cover a slightly different set of legacy codes, and the
two BFFs map some 5xx-class codes to different HTTP statuses (500 in
mobile-bff vs. 503 in web-bff) for the same code set. Both are
pre-existing, narrower in scope than this milestone's mandate, and left
as documented findings rather than silently fixed.

## Security Decisions Summary

- Password reset tokens: opaque, 32-byte random, SHA-256-hashed at rest,
  single-use (atomic claim), 30-minute expiry, invalidate-prior-on-new-request.
- Password reset response is **identical** regardless of account existence
  (status 200, generic body) — no enumeration via status, body, or
  email-send outcome.
- Google `client_secret` never leaves core-api. Web/iOS only hold the
  public `client_id`.
- `redirect_uri` is allowlisted server-side before any Google API call.
- Google account linking requires `email_verified=true` from Google's own
  id_token claim; unverified-email conflicts fail safely without merging
  or crashing.
- Successful password reset revokes all of that user's own existing
  refresh tokens (forces re-login on other devices/sessions) but never
  touches other users' sessions.

## Limitations & What Was Not Verified

This environment has no real SMTP credentials
(`SMTP_HOST`/`SMTP_USER`/`SMTP_PASSWORD` are unset, per `.env.example`
defaults) and no real `GOOGLE_CLIENT_ID`/`GOOGLE_CLIENT_SECRET`. As a
result:

- **Password reset**: token generation, hashing, expiry, single-use
  consumption, and the full request→reset→login round trip were verified
  end-to-end against the real API (mocking only `EmailService.send` to
  capture the token from the email body). Actual SMTP delivery to a real
  mailbox was **not** verified — there is no mail server configured in
  this environment.
- **Google Sign-In**: the account-resolution business logic (all 5
  scenarios above) was verified end-to-end by mocking
  `AuthService._exchange_and_verify_google_code` — the single method that
  encapsulates the real network/crypto work (code→token exchange +
  JWKS signature verification), which is Google's own contract, not
  application logic. The actual live OAuth flow against Google's real
  endpoints was **not** exercised — no live Google Cloud OAuth client
  exists in this environment. iOS's `ASWebAuthenticationSession`-based
  browser flow was verified to compile and its callback-parsing/CSRF-state
  logic was code-reviewed, but the interactive system browser flow itself
  cannot be driven from an automated test.
- No claim is made anywhere in this doc or the milestone report that a
  real email was received or a real Google consent screen was completed.

## Testing

- **core-api**: `tests/test_password_reset.py` (15 tests),
  `tests/test_google_auth.py` (13 tests) — both new. Full existing
  suite (756 tests total) re-run after all changes — 0 regressions.
- **mobile-bff** / **web-bff**: new routes (`/google`, `/forgot-password`,
  `/reset-password`) covered with happy-path and error-passthrough tests
  in both `tests/test_auth.py` files, plus the `REFRESH_TOKEN_*`
  regression tests described above. Full suites: 134 (mobile-bff) / 100
  (web-bff) tests, 0 failures.
- **web**: new pages (`/forgot-password`, `/reset-password`,
  `/auth/google/callback`) each have a dedicated `page.test.tsx`; `login`
  page tests cover the new forgot-password link, the re-entrancy guard,
  and Google-button conditional visibility. Full suite: 113 tests, 0
  failures. `npm run build` and `npm run lint` both clean.
- **iOS**: new `LoginViewModelTests`, `RegisterViewModelTests`,
  `ForgotPasswordViewModelTests`, `ResetPasswordViewModelTests`,
  `AuthEnvironmentTests` (this project had **zero** auth test coverage
  before this milestone). Full suite run via `xcodebuild test` on both
  iphonesimulator and confirmed to build on iphoneos (device SDK): 366
  tests, 0 failures, run twice for determinism. One real test-isolation
  bug was found and fixed during this work: the new tests exercising the
  real `login`/`register`/`googleSignIn` persist path write to the actual
  system Keychain/App Group (unlike every pre-existing test, which uses
  `setUserForTesting()` to bypass persistence entirely) — without
  `tearDown()` cleanup, that leftover Keychain state leaked into
  `TripAssistantViewModelTests`' `withUser: false` scenario in later test
  classes within the same process, causing a real (if narrow) full-suite
  flake. Fixed with matching `setUp()`/`tearDown()` Keychain/App-Group
  clearing in all three new test files that touch the real persist path.

## Environment Variables

See `.env.example` / `services/core-api/.env.example` / `web/.env.example`
for the full set (`SMTP_*`, `PASSWORD_RESET_URL_BASE`,
`PASSWORD_RESET_TOKEN_EXPIRE_MINUTES`, `GOOGLE_CLIENT_ID`,
`GOOGLE_CLIENT_SECRET`, `GOOGLE_ALLOWED_REDIRECT_URIS`,
`NEXT_PUBLIC_GOOGLE_CLIENT_ID`). All are optional — every feature in this
document degrades gracefully (button/link hidden, or endpoint returns a
clean 401/503) when unconfigured, matching the existing
`ApnsClient.is_configured` / `SENTRY_DSN` pattern already used elsewhere
in this project.
