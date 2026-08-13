# Cross-Platform Product Consistency Audit (Milestone 38)

The first milestone to audit iOS and Web *together*, asking whether they
agree on product semantics for the same server-side truth — not whether
they look identical. iOS has been through four dedicated audit milestones
(M34–M37); Web's trip-related flows (beyond auth, covered in M34) had
never been audited this deeply. Backend/BFF changes were made only where
a genuine cross-platform contract bug was found, per this milestone's
explicit allowance.

## Method

Three parallel read-only audits: (1) Web's trip flows (list, detail,
optimizer, itinerary history, apply-history/undo, assistant) — the
biggest coverage gap, (2) Web's auth flow and API client checked against
every bug *class* iOS's M35–M37 found (concurrent-refresh races, pre-auth
endpoints wrongly retried, best-effort calls swallowing 401s, client/
server validation mismatches, cancellation UX, navigation dead ends), and
(3) a direct side-by-side comparison of iOS and Web's handling of the
same operations (error-code mapping, apply/undo trust model, assistant
reference resolution, delete-state propagation) against both BFFs'
actual contracts.

## Already Correct

Both audits of Web's trip flows came back mostly clean — a genuine,
verified result, not an oversight:

- Web's Trip Detail is intentionally read-only for stops/trip (no edit,
  no delete) — the entire class of "multi-day edit-mode" bugs iOS had
  doesn't have a foothold there by design.
- Every mutating flow already has re-entrancy guards, confirmation
  dialogs, and dedicated tests: Optimizer generate/apply, itinerary
  delete, apply-history undo.
- Undo is correctly restricted to the server's own `is_undoable` flag on
  **both** platforms — neither recomputes "is this the latest entry"
  client-side, confirmed by reading both `ItineraryApplyHistoryViewModel.swift`
  and `apply-history/page.tsx` side by side.
- `STALE_UNDO` (409) is handled by typed error code on both platforms,
  never by matching localized message text.
- Assistant reference-chip resolution reads live/current trip data on
  both platforms — no staleness risk found on either side.
- Delete-itinerary → Trip Detail state propagation is correct on both
  platforms, via different (both valid) mechanisms: iOS needed an
  explicit `onDeleted` callback because `TripDetailView` stays alive in
  its `NavigationStack` while a child screen is pushed; Web doesn't need
  one because each route is a distinct page that always remounts and
  refetches — Web gets the same correctness "for free" from its routing
  architecture.
- Web's auth: pre-auth endpoints (login/register/forgot-password/
  reset-password/google) are correctly excluded from the refresh-retry
  path; there's no client-side password-length rule to disagree with the
  server (the only length hint is the placeholder text, which already
  says 8); reset-password's "back to login" does an absolute
  `router.push("/login")`, so — unlike iOS before its M36 fix — it never
  had the "only pops one level" bug; logout clears every auth-relevant
  `localStorage` key and redirects sensibly.
- Both BFFs already agreed on the entire 401-mapped error-code set and on
  their default (unmatched-code) status.

## Genuine Bugs Found & Fixed

### 1. Web's Trip Assistant conversation reset on reference-chip navigation

The exact bug iOS found and fixed in M35 (`TripAssistantViewModel`
recreated on every navigation, losing the conversation) — never ported
to Web, which has an even more pronounced version of it: tapping a
reference chip calls `router.push("/trips/[id]?focusDay=...")`, a
navigation to a completely different Next.js route, which unmounts
`TripAssistantPage` and destroys its `messages` state entirely. There is
no shared layout under `trips/[id]/` that could hold state across the two
routes, so the fix couldn't mirror iOS's exact approach ("lift state to
the parent view" — there is no parent view instance that survives this
navigation on Web).

Fixed using a pattern already established elsewhere in this codebase
(`web/src/lib/googleAuth.ts`'s OAuth `state`/`next` handling):
`sessionStorage`, keyed by trip ID, written on every `messages` change
and read as the initial state on mount. This is not new architecture —
it's the same storage mechanism the app already uses for exactly this
kind of "survive a client-side navigation, scoped to one browsing
session" requirement, deliberately chosen over introducing a new
`layout.tsx`/React Context (either of which would be a larger, riskier
structural change for the same outcome).

**Files**: `web/src/app/trips/[id]/assistant/page.tsx`.

### 2. Web's API client had the same concurrent-refresh race iOS fixed in M35

`web/src/lib/api.ts`'s `refreshAccessToken()` had no in-flight
de-duplication — every `request()` call that hit a 401 independently
called `POST /auth/refresh` with the same stored refresh token. Two
authenticated calls firing in parallel (a real, existing pattern in this
app — e.g. `optimize/page.tsx`'s `Promise.all([loadTrip, getItinerary(...)])`)
that both 401 at once would race: the winner persists a fresh, valid
token pair; the loser's refresh attempt is rejected by the server (core-api's
atomic refresh-token claim, the same mechanism behind the
`REFRESH_TOKEN_RACE_LOST` code), and the *old* code treated that
rejection as "the session is dead" — calling `clearAuthStorage()` and
hard-redirecting to `/login`, **wiping out the tokens the winning request
had just saved seconds earlier.**

Fixed by wrapping `refreshAccessToken()` in a module-level in-flight
promise, mirroring iOS's `AuthEnvironment.inFlightRefresh` (`Task<String?, Never>?`)
adapted to JS: all concurrent callers now share the exact same
`fetch("/auth/refresh")` call and its result, so this client can
structurally never issue two simultaneous refresh requests.

**Files**: `web/src/lib/api.ts`.

### 3. `FORBIDDEN` error code mapped to 403 on iOS/mobile-bff but silently fell to 400 on web-bff

Same core-api condition (a protected endpoint hit with *no* Authorization
header at all — FastAPI's built-in `HTTPBearer` dependency raising its
own 403, distinct from an invalid/expired token, which core-api already
turns into 401) produced a correct 403 for iOS users and an incorrect,
generic 400 "Bir hata oluştu" for Web users. `mobile-bff` already mapped
both `PERMISSION_DENIED` and `FORBIDDEN` to 403; `web-bff` only checked
`PERMISSION_DENIED`. Fixed by adding `FORBIDDEN` to web-bff's 403 set and
giving it its own message (distinct from `PERMISSION_DENIED`'s, since
it's a different underlying condition — no session at all vs. a valid
session lacking permission).

**Files**: `services/web-bff/app/core/error_wrapper.py`.

### 4. `SERVICE_UNAVAILABLE` error code mapped to 503 on web-bff but silently fell to 400 on mobile-bff

The mirror image of #3: both BFFs already carry a *message* for this
code (implying it was always an anticipated one), and web-bff correctly
maps it to 503 — but mobile-bff's 500-class set never included it, so
the same core-api condition produced a correct 5xx for Web and a
misleading 400 "geçersiz istek" for iOS. Fixed by adding it to
mobile-bff's existing 500-set (mapped to 500, matching mobile-bff's own
established convention for this class of code — not to 503, which would
require reconciling a separate, pre-existing, already-documented 500-vs-503
convention difference between the two BFFs that this milestone did not
set out to fix; see "Deliberately Left Untouched" below).

**Files**: `services/mobile-bff/app/core/error_wrapper.py`.

### 5. Google Sign-In cancellation on Web used the same alarming styling as a genuine failure

Lower-severity UX inconsistency: the cancellation message text was
already correctly worded ("Google girişi iptal edildi veya reddedildi."),
but rendered through the identical `bg-destructive`/red-icon/
`role="alert" aria-live="assertive"` treatment used for real failures
(CSRF state mismatch, account-linking rejection). A user who simply
clicked "Cancel" on Google's own consent screen saw the same visual
alarm as someone whose login was actually broken. Fixed by introducing a
distinct `GoogleCancelledError` class (thrown for the `error` query-param
case, caught separately) and a neutral, non-alarming presentation for
that specific case — no destructive styling, no `role="alert"`.

**Files**: `web/src/app/auth/google/callback/page.tsx`.

## Deliberately Left Untouched

- **`SHARE_NOT_FOUND` missing from web-bff's 404 set** — found alongside
  #3/#4 during the same comparison, but `ShareNotFoundException` is
  defined in core-api yet **never actually raised** anywhere in the
  current codebase (only `ShareTokenInvalidException` is, which both
  BFFs already handle identically). This was still added to web-bff's
  404 set for direct consistency with mobile-bff (a one-line, zero-risk
  mirror of an existing pattern), even though it's currently a dead code
  path — closing the landmine now is cheap; leaving it would mean the
  BFFs silently re-diverge the moment core-api ever does raise it.
- **The pre-existing 500-vs-503 convention difference between the two
  BFFs** for the shared `{DATABASE_ERROR, ML_SERVICE_UNAVAILABLE,
  INTERNAL_SERVER_ERROR, ASSISTANT_UNAVAILABLE}` code set (mobile-bff:
  500, web-bff: 503) — this was already identified and deliberately left
  alone in Milestone 34's own final report as a pre-existing,
  independent-of-any-new-work asymmetry. Fix #4 above intentionally
  followed mobile-bff's own existing convention (500) rather than trying
  to additionally harmonize this older, separate difference, which is a
  larger decision (which BFF is "right"?) outside this milestone's scope
  of fixing the one missing-code contract bug.
- **All of M35–M37's own already-reviewed-and-deferred iOS findings**
  (session-expired toast, optimizer-cache-survives-logout, Dynamic Type,
  etc.) — re-confirmed still correctly out of scope, not re-litigated.

## Testing

Baseline going in: iOS 399/399, mobile-bff 134/134, web-bff 100/100, Web
113/113. 8 new/modified tests added:

- `web/src/lib/api.test.ts` (new file) — the first direct test of
  `api.ts`'s `request()`/`refreshAccessToken()` internals (previously
  only ever exercised indirectly through fully-mocked page tests).
  Deterministically reproduces two concurrent 401s and asserts exactly
  one `/auth/refresh` call is made and both callers receive the
  refreshed token. Verified this test genuinely catches the regression
  by temporarily reverting the fix and confirming it fails (2 calls
  instead of 1), then restoring the fix and confirming it passes.
- `web/src/app/trips/[id]/assistant/page.test.tsx` (+1) — unmounts and
  re-renders the page (the closest deterministic equivalent to real
  client-side navigation away and back) and asserts the prior
  conversation is still visible, not reset to the empty suggested-prompts
  state. Same before/after verification as above: fails without the fix,
  passes with it.
- `web/src/app/auth/google/callback/page.test.tsx` (updated) — asserts
  the cancellation case renders with no `role="alert"` element, locking
  in the neutral-treatment fix rather than just the wording.
- `services/mobile-bff/tests/test_auth.py` (+1) — `SERVICE_UNAVAILABLE`
  maps to 500.
- `services/web-bff/tests/test_auth.py` (+2) — `FORBIDDEN` maps to 403,
  `SHARE_NOT_FOUND` maps to 404.

## Build / Test Results

- **iOS**: simulator test suite 399/399 (run once; unchanged from M37's
  baseline since no iOS files were touched this milestone), device SDK
  build clean. Re-run specifically to confirm zero drift from the
  cross-platform BFF changes.
- **Web**: `npm run lint` clean (one pre-existing, unrelated warning),
  `npm run build` (typecheck + production build) clean, all 13 route
  pages generated successfully, `npm test` 115/115.
- **mobile-bff**: 135/135 (134 baseline + 1 new).
- **web-bff**: 102/102 (100 baseline + 2 new).
- **core-api**: full suite re-run for completeness even though no
  core-api files were touched this milestone (only the two BFFs, which
  are separate services) — see final report for the exact count.

## Real Verification Status

No interactive browser/simulator automation tooling is available in this
environment. What was actually run: the full deterministic test suites
above (iOS, Web, mobile-bff, web-bff, core-api), `npm run build`'s static
generation of all Web routes, and iOS's simulator + device SDK builds. No
claim is made of a manual browser walkthrough or simulator tap-through —
consistent with every prior milestone in this series.

## Remaining Limitations

- The Web assistant's `sessionStorage`-based conversation persistence is
  tab/session-scoped, not cross-device or cross-tab — this matches the
  scope of the bug being fixed (survive in-app navigation) and doesn't
  claim to solve cross-device conversation sync, which was never a
  stated requirement.
- The pre-existing 500-vs-503 BFF convention difference (see "Deliberately
  Left Untouched") remains unreconciled — a legitimate candidate for a
  future, dedicated decision if it's ever judged worth unifying.
- No interactive UI verification was possible in this environment for
  either platform, per the section above.
