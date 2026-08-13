# Production Readiness & Data Integrity Audit (Milestone 39)

Not a feature milestone. Four parallel read-only audits traced the complete
lifecycle of authentication/token-refresh/password-reset/Google Sign-In,
video upload/processing, trip creation/list/detail/deletion/assistant
navigation, and itinerary generate/apply/delete/history/undo — across iOS,
Web, both BFFs, and core-api — against an 14-scenario failure matrix (4xx/5xx,
timeout, dropped connection, double-submit, concurrent requests, navigate-away,
logout-mid-request, token expiry, backgrounding, ViewModel teardown). Every
finding was classified as a genuine bug (fixed), intentional/cosmetic (left),
unconfirmed (flagged, not guessed), or requiring a product decision (deferred).
No AI/RAG/assistant architecture, MCP, agents, UI redesign, or Share Extension
code was touched, per this milestone's explicit scope.

## 1. What Was Already Production-Safe

Verified correct by tracing the actual current code, not assumed from prior
milestones' docs:

- **Concurrent-refresh de-duplication** on both iOS (`AuthEnvironment.inFlightRefresh`)
  and Web (`api.ts`'s in-flight promise) — still correct.
- **Refresh-token reuse detection** — atomic single-`UPDATE...WHERE...IS NULL`
  claim (`revoke_if_active`), not read-then-write.
- **Password-reset token consumption** — atomic `mark_used_if_active`, same pattern.
- **Google/Apple account-linking decision tree** — verified account-email
  collision, unverified-email rejection, and cancellation handling all correct
  on both platforms.
- **Video pipeline idempotency** — `save_results` is a single-row overwrite
  (safe on Celery retry); `sync_from_video`'s place/place-save dedup is
  correctly guarded by lookup + a real DB unique constraint.
- **FK cascade/SET NULL semantics** across trips → trip_stops → itineraries →
  itinerary_stops → apply_history, and video → place/place_save — all verified
  against actual migrations, not just model comments.
- **Apply-history "latest-only" undo rule** — real server-enforced query
  condition (`ORDER BY id DESC` + equality check), never recomputed
  client-side on either platform; naturally safe under a naive client retry
  (a lost-response retry finds a new "latest" row and gets a clean `409`).
- **Anti-enumeration 404 unification** for itinerary access — a real
  `resolve_access` check, not just documented.
- **Trip Assistant reference-chip resolution** — both platforms re-derive the
  target stop from live trip data on tap, never trust a captured value.
- **Delete-itinerary transaction** — `applied_itinerary_id` clearing and the
  itinerary/stop delete already happened in one commit; no crash window existed here.

## 2–4. Genuine Bugs Found, Fixes, and Why

### Auth / Session

**iOS: a refresh completing after logout could resurrect the session.**
`AuthEnvironment.performRefresh()` unconditionally applied a successful
refresh response via `persist()`, with no check for a logout that happened
while the request was in flight. Concrete path: a view's `.task` triggers a
refresh on an expired token; the user taps "Log Out" before the network call
returns; `logout()` clears Keychain/state immediately; the refresh then
succeeds and `persist()` silently rewrites a *new, valid* token pair,
undoing the logout. **Fix**: a `sessionEpoch` counter, bumped by `logout()`
and captured at the start of `performRefresh()` — the result is discarded if
the epoch changed while awaiting the network call. `ios/TripClipApp/Features/Auth/AuthEnvironment.swift`.

**core-api: password reset could change the password without revoking old sessions.**
`reset_password()` ran `update_password` then `revoke_all_for_user` as two
separate commits. A crash/connection-loss between them left the password
changed but old refresh tokens — including one an attacker might hold —
still valid, defeating the method's own stated security purpose. **Fix**:
reordered to revoke first, then update — a crash now always fails on the
safe side (sessions killed, password unchanged, user retries) instead of the
unsafe side. `services/core-api/app/application/services/auth_service.py`.

**iOS: APNs device-token registration silently stopped working after ~30 minutes.**
`AppDelegate.sendDeviceTokenToBackend` built its own `APIClient()` with no
`refreshHandler`, so any 401 (an expired access token, common on a cold
relaunch) threw immediately and was swallowed by a bare `catch`, with no
retry path — push notifications quietly never registered for that install.
**Fix**: `AppDelegate` now uses the same shared `APIClient` instance
`AuthEnvironment` wires its `refreshHandler` onto, so this call gets the
same 401→refresh→retry behavior as every other authenticated request.
`ios/TripClipApp/App/AppDelegate.swift`, `TripClipApp.swift`.

### Upload / Processing

**iOS: a 404 (deleted video) during progress polling was treated as transient.**
`ProcessingViewModel.fetchProgress()` only special-cased 401; a 404 (the
video deleted from another device — the same account can be logged in on
multiple devices) fell into the generic "not permanent, keep polling" catch.
The user saw "processing, please wait" until the 300s client timeout, then
could tap "keep waiting" and poll a nonexistent video for another 5 minutes.
**Fix**: 404 now stops polling immediately with a clear "this video no
longer exists" message. `ios/TripClipApp/Features/Processing/ProcessingViewModel.swift`.

**core-api: a malformed video could hang the entire processing queue forever.**
The documented worker command (`--pool=solo`, per CLAUDE.md) does not enforce
Celery's `task_soft_time_limit`/`task_time_limit` — that mechanism requires a
separate process to signal, which `solo` doesn't have. The frame-extraction
stage's `ffmpeg.probe()`/`ffmpeg....run()` calls have no subprocess timeout of
their own. A corrupt/truncated upload could hang the ffmpeg subprocess
indefinitely; since `solo` processes one task at a time, this stalled the
*entire* queue for *every* user, with no automatic recovery. **Fix**: a
`SIGALRM`-based `_FFmpegTimeoutGuard` (30s for probe, 180s for extraction),
active only on the main thread (where these calls actually run, before the
parallel AI-stage `ThreadPoolExecutor`) — a timeout now raises a normal
exception, which the task's existing `except Exception`/retry/`mark_failed`
handling already processes correctly.
`services/core-api/app/core/services/video_processor.py`.

### Trip Lifecycle

**iOS: a trip deleted elsewhere kept rendering as if still live.**
`TripDetailViewModel.load()` set `error` on failure but never cleared a
previously-loaded `trip`. If the trip was deleted from another
screen/device and the user pulled to refresh (or any mutation callback
re-triggered `load()`), the screen silently kept showing the stale trip —
map, stop list, and toolbar actions all still interactive — with no visible
error, until an edit attempt failed with a generic message. **Fix**: `trip`
is now cleared specifically on a 404 (`.notFound`) — other, transient
errors still preserve the stale view, matching every sibling screen's
existing convention. `ios/TripClipApp/Features/Trips/TripDetailViewModel.swift`.

**iOS: a failed stop edit could overwrite a concurrently-refreshed newer state.**
`persistDay()`'s failure path restored the pre-edit local `snapshot`
unconditionally. If a parallel pull-to-refresh or mutation callback (apply/
delete/undo, all of which call `load()`) updated `trip` while the edit
request was in flight, a subsequent failure discarded that newer state and
replaced it with the older snapshot — silently. **Fix**: on failure, the
trip is now re-fetched from the server instead of restored from the local
snapshot (falling back to the snapshot only if the re-fetch itself fails) —
the server remains the single source of truth. Same file.

**core-api: concurrent stop reorders could silently discard each other.**
`update_stop_order` had no locking — two concurrent `PATCH .../order` calls
(an owner + editor collaborator, or the same user on two devices) could
interleave their delete+insert in an undefined order, with neither caller
told their edit was discarded. **Fix**: a `SELECT ... FOR UPDATE` lock on the
`Trip` row serializes concurrent reorders — the outcome is still
last-write-wins (an accepted, pre-existing product semantic, not changed
here) but is now deterministic rather than racy.
`services/core-api/app/infrastructure/repositories/sql_trip_repository.py`.

### Itinerary Integrity

**core-api: concurrent apply/undo had no locking — could corrupt the audit trail and lose a committed apply.**
`apply_itinerary` and `undo_apply_history` each read "the current state"
(`applied_itinerary_id`, the stops snapshot, the "latest" apply-history row)
and later wrote based on that read, with no row lock between the two. Two
concurrent applies could both read the same stale starting point; whichever
committed second overwrote the first's stops and wrote a history row that
made the first apply vanish from the audit trail entirely — and a subsequent
undo of the second entry would then restore to a state older than intended,
silently losing the first apply. The same gap made `undo_apply_history`'s
"is this the latest entry?" staleness check a genuine TOCTOU: a concurrent
apply could commit a newer entry between the check and the mutation.
**Fix**: both methods now take `SELECT ... FOR UPDATE` on the `Trip` row
before reading any "current state," serializing all apply/undo/delete calls
for the same trip — the staleness check is now always evaluated against
truly current data.
`services/core-api/app/infrastructure/repositories/sql_optimization_repository.py`.

**core-api: deleting an itinerary while it was being applied produced an opaque 500.**
If a delete committed between an in-flight apply's read and its own commit,
the apply's `INSERT` into `trip_itinerary_apply_history` referenced an
itinerary ID that no longer existed, violating the FK and surfacing a
generic `INTERNAL_SERVER_ERROR` instead of a clean, already-defined error
status. **Fix**: closed by the same `Trip`-row lock above — `delete_itinerary`
now also takes it, as early as possible (before any child-row cleanup), so
the two operations are fully serialized; whichever runs second now takes its
own existing, clean error path (e.g. `apply`'s "empty" status when its
itinerary's stops have vanished) instead of racing into an FK violation.
Same file.

## 5. Files Changed

- `ios/TripClipApp/Features/Auth/AuthEnvironment.swift`
- `ios/TripClipApp/App/AppDelegate.swift`
- `ios/TripClipApp/App/TripClipApp.swift`
- `ios/TripClipApp/Features/Processing/ProcessingViewModel.swift`
- `ios/TripClipApp/Features/Trips/TripDetailViewModel.swift`
- `services/core-api/app/application/services/auth_service.py`
- `services/core-api/app/core/services/video_processor.py`
- `services/core-api/app/infrastructure/repositories/sql_trip_repository.py`
- `services/core-api/app/infrastructure/repositories/sql_optimization_repository.py`

## 6. Tests Added

- `ios/TripClipAppTests/AuthEnvironmentTests.swift` (+1) —
  `test_refreshCompletingAfterLogout_doesNotResurrectSession`: deterministic,
  gate-based reproduction of the logout/in-flight-refresh race.
- `ios/TripClipAppTests/ProcessingViewModelTests.swift` (+1) —
  404 now stops polling immediately with the correct terminal message.
- `ios/TripClipAppTests/TripDetailViewModelTests.swift` (+3) — stale-trip
  cleared on 404 / preserved on transient error; `persistDay` failure
  re-fetches from server rather than restoring a stale snapshot (uses a new
  `FakeAPIClient.results` queue, added to the shared test double, to give
  the edit call and the refetch call different responses).
- `services/core-api/tests/test_password_reset.py` (+1) — password update
  failing still leaves the user's old sessions revoked (the reordering fix).
- `services/core-api/tests/test_video_processor.py` (+3) — `_FFmpegTimeoutGuard`
  raises on a real timeout, doesn't raise when work finishes in time, and is
  a documented no-op off the main thread.

The `SELECT ... FOR UPDATE` additions (trip stop-order, apply/undo/delete)
were **not** given a concurrency test — the project's test suite runs
against SQLite (per an existing comment in `sql_trip_repository.py`), which
does not enforce row-level locking; a "concurrency" test there would not
exercise the real lock and would be misleading. These were verified by (a)
re-running the full existing suite to confirm zero behavioral change for the
sequential/single-request case, and (b) direct code review of the lock
placement relative to every read it's meant to protect. The AppDelegate
device-token wiring fix also has no dedicated test — no test infrastructure
exists for `UIApplicationDelegate` in this project (same limitation noted
throughout M35–M38 for structural/navigation wiring) — verified by code
review and by the clean device SDK build.

## 7. Full Test Results

| Suite | Result |
|---|---|
| core-api | **760/760** passed |
| mobile-bff | **135/135** passed |
| web-bff | **102/102** passed |
| Web | **115/115** passed (unchanged — no Web-side fixes this milestone) |
| iOS (simulator) | **404/404** passed (399 baseline + 5 new) |

## 8. Build / Typecheck / Lint Results

- **iOS**: `xcodegen generate` clean; simulator test build clean; device SDK
  build (`generic/platform=iOS`) succeeded — with `CODE_SIGNING_ALLOWED=NO`,
  since this environment has no provisioning profiles installed for
  `com.sardogan.TripClipAI`/`.ShareExtension` (an environment/credentials
  gap, not a code issue; compilation itself is clean for both targets).
- **Web**: `npm test` 115/115; `npm run lint` — 1 pre-existing warning
  (`analyze/[id]/page.tsx`, unrelated to this milestone, already present
  before it), 0 errors; `npm run build` — clean, all 19 routes generated.
- **Backend**: full `pytest` suites above, no new warnings beyond pre-existing
  deprecation notices from third-party packages (thop/distutils, python-multipart).

## 9. Database / Integrity Findings

- FK cascade/SET NULL behavior verified correct at the migration level for
  trips → trip_stops (CASCADE), trips → trip_itineraries (CASCADE),
  trip_itineraries → trip_itinerary_stops (CASCADE), apply-history's
  `itinerary_id`/`previous_itinerary_id` (SET NULL — history rows survive
  itinerary deletion by design), and video → place/place_save (SET NULL —
  derived Place data survives video deletion by design).
- `SqlTripRepository.delete_trip`'s manual child-row cleanup (needed because
  the SQLite test environment doesn't enforce `PRAGMA foreign_keys=ON`)
  doesn't include `trip_itineraries`/`trip_itinerary_stops`/apply-history in
  its explicit list, but production Postgres's real DB-level CASCADE already
  handles this correctly regardless — a test-environment/comment-accuracy
  gap only, not a production data-integrity bug. Left as-is (see §12).
- No transaction wrapped multi-row writes in a way that could leave a
  *partially* written itinerary — `save_itinerary`/`apply_itinerary`/
  `undo_apply_history` are each a single flush-then-commit.

## 10. Auth / Session Findings

See §2–4 for the two fixed bugs. Additionally, confirmed **not** bugs:

- A crash between refresh-token revoke and re-issue (two separate commits in
  the rotation path) forces a re-login but has no security/corruption
  impact — an accepted trade-off of rotating-refresh-token designs, not
  something a two-phase-commit rewrite is warranted for here.
- Web's `logout()` does a full page navigation, which structurally
  prevents the iOS-equivalent "resurrected session" race by tearing down
  the JS execution context — verified, not just assumed.

## 11. Retry / Idempotency Findings

Classified every mutation in scope:

| Operation | Classification |
|---|---|
| Login / Register | non-idempotent, protected by unique constraint |
| Token refresh | intentionally non-idempotent (rotation) |
| Logout | naturally idempotent |
| Forgot password | idempotent from the caller's view (generic response either way) |
| Reset password | correctly non-idempotent, single-use, atomic |
| Google/Apple sign-in | non-idempotent, protected by unique constraints |
| Video upload | **non-idempotent, no protection** — see below |
| Trip creation | **non-idempotent, no protection** — see below |
| Trip stop reorder | naturally idempotent per-request; now safe under concurrency (§4) |
| Trip delete | naturally idempotent |
| Itinerary generate | non-idempotent by design, intentionally safe (always a new row, never overwrites) |
| Itinerary apply | idempotent in end-state; audit trail now safe under concurrency (§4) |
| Itinerary delete | naturally idempotent |
| Undo | safe under naive retry; now safe under concurrency (§4) |

**Not fixed, flagged as needing a product decision (see §13):** neither video
upload nor trip creation has a client-generated idempotency key. A genuine
network timeout/dropped-connection followed by a client retry can produce two
`Video`/`Trip` rows for what the user believes was one action. This is a real,
code-confirmed gap — not fixed here because closing it properly needs a new
concept (an idempotency key honored server-side), which is an architecture
addition, not a bug fix, and explicitly out of this milestone's "do not add
speculative concurrency protection" / "do not create migrations without a
demonstrated integrity problem" scope boundary for anything beyond the
already-demonstrated locking gaps fixed above.

## 12. Intentionally Left Untouched

- **Register / concurrent duplicate-email race** → generic `DATABASE_ERROR`
  (503) instead of an "email taken" message. No corruption (unique
  constraint holds, transaction rolls back cleanly) — cosmetic error-message
  quality only.
- **Forgot-password / concurrent requests** → can leave two valid reset
  tokens instead of the documented "only the latest" invariant. Not a
  security issue (still requires inbox access) and self-heals on next use.
- **Google Sign-In / concurrent brand-new-account race** → unhandled 500
  instead of `register()`'s equivalent clean `DatabaseException`. No
  duplicate user is ever created (DB constraint holds) — an error-shape
  inconsistency, not an integrity issue.
- **Daily upload quota consumed even if the upload never completes** — minor
  UX nuisance, quota is generous (20/day default).
- **Itinerary apply retried after a client timeout** — produces a harmless,
  spurious no-op history row (new state equals old state).
- **iOS doesn't auto-refresh the apply-history list on a `STALE_UNDO` 409**
  the way Web does — an extra manual pull-to-refresh, no data loss.
- **`delete_trip`'s manual-cleanup comment/list gap** — see §9; a
  test-environment/documentation accuracy issue, zero production impact.
- **The pre-existing mobile-bff/web-bff 500-vs-503 convention difference**
  for the shared `DATABASE_ERROR`/`ML_SERVICE_UNAVAILABLE`/etc. code set —
  already identified and deliberately deferred in Milestone 34's own report;
  not re-litigated here.
- **Main-app video upload uses a foreground `URLSession`, not a background
  one** — likely fails cleanly (a normal, already-handled `.failed` state,
  not a corrupted one) if the app is backgrounded mid-upload. A proper fix
  means adopting a background-session architecture for the main app
  (mirroring the Share Extension's separate `BackgroundUploader`, which
  operates under different constraints — App Group state, a different
  target) — a real architecture decision, not a small fix, so it's
  deferred rather than attempted here.

## 13. Remaining Limitations

- **No idempotency protection for video upload or trip creation** (§11) — the
  single largest remaining data-integrity gap this audit found. Needs a
  product decision on the idempotency-key mechanism before it can be closed.
- **No background-session support for main-app upload** (§12) — deferred,
  same reasoning.
- Two structural findings could not be *fully* confirmed or ruled out by
  static reading alone and were deliberately not guessed at:
  - `TripDetailView`'s several independent parallel `.task`s on initial load
    only read (never write) shared state in conflicting ways, which looks
    safe, but true interleaving-order guarantees aren't something static
    reading can fully certify.
  - The Trip Assistant context builder's two sequential, non-transactional
    reads (trip, then optionally its applied itinerary) could theoretically
    span a concurrent apply/undo — but itinerary rows are immutable once
    created, the only cross-read state affects non-critical enrichment
    fields, and a deleted-itinerary race already falls back gracefully to
    trip-only context. Bounded, not proven torn-free.
- No interactive browser/simulator UI automation is available in this
  environment — verification relied entirely on the deterministic test
  suites, static builds, and code review above, consistent with every prior
  milestone in this series.

## 14. Recommended Next Milestone

An idempotency-key design for the two non-idempotent, unprotected mutations
identified in §11/§13 (video upload, trip creation) — the one concrete,
demonstrated integrity gap this audit found but explicitly did not fix, since
it requires a product/architecture decision rather than a bug fix.
