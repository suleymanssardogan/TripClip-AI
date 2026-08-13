# iOS Product UX & System Consistency Audit (Milestone 35)

A full-flow audit of the iOS app (auth → trip list → trip detail → optimizer
→ apply/undo/history → assistant → logout), followed by fixes for the
genuine bugs and inconsistencies found. Strictly iOS-scoped — no backend,
Web, or AI-architecture changes were needed or made.

## Method

Before any code was touched, three parallel read-only audits covered: (1)
trip list/detail, optimizer, and apply/undo/history as a state machine, (2)
Trip Assistant UI/ViewModel, the M34 auth integration, and the network/API
client layer, and (3) cross-screen UI consistency and accessibility. Each
audit classified findings as confirmed bug, UX inconsistency, already
correct/intentional, or needs-more-evidence — only the first two categories
were acted on.

## Bugs Found & Fixed

### 1. Trip Assistant conversation lost on reference-chip navigation

`TripAssistantView` owned its `TripAssistantViewModel` as `@State`. Tapping
a reference chip calls `onFocusStop` then `dismiss()`, popping the view;
`TripDetailView`'s `NavigationLink` destination is re-evaluated on next
entry, constructing a **new** `TripAssistantViewModel()` and silently
discarding the whole conversation. Fixed by hoisting the ViewModel to
`TripDetailView`'s own `@State` (`assistantVM`) and passing the same
instance into `TripAssistantView(vm:)` — the conversation now survives for
as long as the user stays on that trip's detail screen, and correctly
resets when they leave the trip entirely (a new `TripDetailView` per trip).

### 2. Concurrent access-token refresh race could force-log-out a valid session

`AuthEnvironment.refreshTokens()` had no serialization: every concurrent
401 (e.g. `TripDetailView`'s three parallel `.task`s all firing at once
against an expired token) independently read the same refresh token from
Keychain and independently called `/auth/refresh`. One call would succeed
and rotate the token pair; the other, now using a stale/consumed refresh
token, would fail — and unconditionally triggered `handleUnauthorized()`,
deleting the session the first call had *just* successfully refreshed.
core-api's own `REFRESH_TOKEN_RACE_LOST` error code (mapped to 401 in both
BFFs since M34) anticipates exactly this class of race.

Fixed by adding a single in-flight `Task<String?, Never>?`
(`inFlightRefresh`) that all concurrent callers share — structurally, this
client can never issue two simultaneous `/auth/refresh` requests. This
eliminates the client-caused race entirely rather than trying to
special-case which error codes are "safe to ignore." Also closed a related
gap: `restoreSession()` (called from `init()`, on app cold-start) never
checked token expiry — it now does, and proactively kicks off a refresh
through the same serialized path if the restored token is already expired.

### 3. 401-retry wrapper applied to pre-auth endpoints

`APIClient.send()`'s 401→refresh→retry wrapper excluded only `.refresh`
and `.login`. `.register`, `.appleSignIn`, `.googleSignIn`,
`.forgotPassword`, and `.resetPassword` are all called with `token: nil`
(no session yet) and can legitimately 401 for reasons unrelated to session
expiry (`GOOGLE_EMAIL_NOT_VERIFIED`, `PASSWORD_RESET_TOKEN_EXPIRED`, etc.,
per mobile-bff's error map). Left unexcluded, a domain-specific 401 on one
of these screens would trigger a pointless refresh attempt and, in the
edge case where a *different* valid session token happened to exist in
Keychain, could redundantly refresh/rotate that unrelated session as a
side effect. Fixed by extending the exclusion list to all pre-auth
endpoints.

### 4. `TripsListView` showed stale rows after trip deletion/edits

Unlike `HomeView` (which already fixed the identical problem for its own
list via `.onChange(of: navPath.count)`), `TripsListView` only loaded data
once via `.task`. Deleting a trip (or editing its stops) in
`TripDetailView` and returning left the stale row in the list — tapping it
re-pushed a now-404'ing `TripDetailView`. `TripsListView` doesn't own a
`NavigationStack` (it's pushed as a plain `NavigationLink` destination from
`LibraryView`), so the `navPath`-based fix doesn't apply here; fixed with
`.onAppear` (which reliably fires when returning from a pushed child, not
just on the view's first appearance).

### 5. Deleting an itinerary from history never told Trip Detail to refresh

`ItineraryHistoryView`'s delete only updated its own local list. Deleting
the last remaining itinerary left `TripDetailView`'s "Optimizasyon
Geçmişi" toolbar icon visible (leading to an empty-state dead end).
Deleting the *currently applied* itinerary — which core-api clears
`Trip.applied_itinerary_id` for server-side — left the "uygulandı" banner
showing for an itinerary that no longer existed. Fixed with a new
`onDeleted` callback, mirrored from the existing `onApplied`/`onChanged`
pattern already used by `ItineraryApplyHistoryView` and
`TripOptimizerView`; `TripDetailView` now reloads both the trip and its
`hasItineraryHistory` flag after a successful delete.

### 6. Successful Optimizer apply left the user on the wrong screen

`TripOptimizerView`'s "Tamam" handler calls `onApplied?()` then its own
`dismiss()` — but `TripOptimizerConfigView` (one level up, "select places
& configure duration") had a `@Environment(\.dismiss)` it never called.
After a successful "Trip'e Uygula", the user landed back on the config
screen (with an active "Optimize Et" CTA), not on `TripDetailView`. Fixed
by wrapping the `onApplied` closure passed into `TripOptimizerView` so it
also dismisses `TripOptimizerConfigView`, collapsing the whole
Config→Result chain back to `TripDetailView` in one motion.

### 7. Core Data "Geçmiş Geziler" deleted a record with no confirmation

`HistoryView` (the offline/local history screen) deleted a `SavedVideo`
record immediately on swipe, with no `.confirmationDialog` — the only
destructive action in the app that skipped this, inconsistent with every
other delete/logout/undo flow (all of which already use the same
`.confirmationDialog` + "Sil"/"Vazgeç" pattern). Fixed to match.

### 8. `ItineraryHistoryView` delete guard was per-row, not global

`ItineraryHistoryViewModel.deleteItinerary` already has a VM-level
re-entrancy guard (`deletingID == nil`), but the UI only visually disabled
the row being deleted. Swipe-deleting a second row while the first delete
was in flight silently hit the guard and returned `false` — no error, no
busy indicator, no feedback. `ItineraryApplyHistoryView`'s equivalent undo
flow already disables *all* rows while any undo is in flight
(`.disabled(vm.undoingID != nil)`); `ItineraryHistoryView` now matches
that pattern.

### 9. `ProcessingViewModel` didn't stop polling on 401

Every other ViewModel in the app checks `apiError.isUnauthorized` and
stops on 401. `ProcessingViewModel.fetchProgress()` caught all errors
generically and kept polling every 2 seconds for up to 300 seconds after
the session had already ended. The global logout still happens correctly
(triggered inside `AuthEnvironment.refreshTokens()`, reached via
`APIClient.send`'s own retry wrapper) — this fix only stops the
now-pointless polling loop early, matching the codebase-wide convention.

## Accessibility Gaps Fixed

- `LocationCard`'s edit-mode move-up/move-down/delete buttons (the only
  way to reorder or delete a stop in both `TripDetailView` and
  `ResultsView`) were icon-only with no `accessibilityLabel` — VoiceOver
  announced only the SF Symbol's generic name ("trash", "chevron up").
- `HomeView`'s logout icon and `TripDetailView`'s delete-trip toolbar icon
  (the two most consequential icon-only destructive actions) lacked
  labels.
- `LibraryRowView` and `TripStopSelectionRow` (multi-select place/stop
  rows) conveyed selection purely via a filled/outline icon swap with no
  `.isSelected` accessibility trait — a VoiceOver user had no way to hear
  which items were currently selected.
- `ItineraryStopRow` (Optimizer Result's stop list) had no accessibility
  treatment at all — no combined label, no selected-state trait — despite
  the same selected/unselected concept being explicitly signaled visually
  elsewhere in the app via both color and shape.

All four now follow the existing `.accessibilityElement(children: .combine)`
+ `.accessibilityAddTraits(.isSelected)` / `.accessibilityLabel(...)`
conventions already established by `TripDetailView`'s day chips,
`OptimizerRouteMapSection`'s day/transport chips, and `TripAssistantView`'s
message bubbles.

## Findings Deliberately Left Untouched

- **Day-chip tap clears vs. preserves the selected stop** in
  `OptimizerRouteMapSection` vs. `TripDetailView` — both behaviors are
  independently documented as deliberate in `docs/ios-trip-optimizer.md`.
  Changing either would contradict an existing, tested design decision;
  this is a minor cross-screen inconsistency between two intentional
  choices, not a bug.
- **Swipe-to-delete vs. long-press-context-menu** for row deletion
  (`ItineraryHistoryView`/`HistoryView` vs. `HomeView`'s plan list) — both
  work correctly; changing either is a gesture-discovery preference, not a
  correctness issue, and the milestone's own scope explicitly excludes
  cosmetic changes made just to increase consistency for its own sake.
- **`ItineraryApplyHistoryView`'s missing `?? fallback`** on one error
  text — confirmed to have zero behavioral effect today
  (`APIError.errorDescription` never returns `nil`); not worth the churn.
- **Share Extension's independent token-refresh path**
  (`BackgroundUploader.ensureFreshToken()`, App-Group `UserDefaults`,
  entirely separate from `AuthEnvironment`'s Keychain-based refresh) — a
  cross-process race between the main app and the Share Extension was
  flagged as *plausible but unconfirmed* and explicitly out of this
  milestone's primary scope (`iOS → Mobile BFF → core-api`, not the Share
  Extension target). Left as a documented risk for a future, dedicated
  audit rather than expanding scope here.

## Testing

16 new tests added (382/382 passing, run twice for determinism):

- `APIClientTests.swift` (new) — first-ever direct test of `APIClient.send`'s
  real 401→refresh→retry wrapper, via a new `MockURLProtocol` support file
  (`FakeAPIClient` never exercised this code path). Covers: successful
  retry with a refreshed token, a failed refresh not looping, the
  `.refresh` endpoint's own 401 not retrying itself, `.resetPassword` and
  `.googleSignIn` never triggering a refresh attempt, and both error
  envelope shapes (mobile-bff flat, core-api/web-bff nested) decoding
  correctly.
- `AuthEnvironmentTests` (+1) — deterministic regression test for the
  concurrent-refresh race, using `FakeAPIClient`'s gate mechanism to force
  two `validAccessToken()` calls to overlap and asserting exactly one
  `/auth/refresh` request was made and the winning session survived.
- `TripAssistantViewModelTests` (+1) — pins the reference-semantics
  assumption the conversation-persistence fix depends on.
- `TripsListViewModelTests.swift` (new) — this ViewModel had zero prior
  coverage; added baseline tests including the re-entrancy guard, made
  more important now that `.onAppear` calls `load()` more frequently.
- `ProcessingViewModelTests.swift` (new) — regression test for the
  stop-polling-on-401 fix.

**Limitation**: several fixes are pure SwiftUI navigation/state-ownership
changes (the assistant conversation hoist, `TripsListView`'s `.onAppear`,
the `onDeleted`/dismiss callback wiring, the confirmation dialogs) that
aren't reachable by this project's XCTest unit-test target — there is no
UI test target in this project. These were verified by code review and by
the fact the underlying ViewModel contracts they depend on (e.g.
`deleteItinerary`'s `Bool` return, already thoroughly tested) hold. No
interactive multi-screen UI walkthrough was performed — see the milestone
final report for what real verification *was* done (build/install/launch
+ a launch screenshot).

---

# Milestone 36 — UX, Navigation & State Consistency

A follow-up audit focused on navigation-stack correctness, cross-screen
state consistency beyond what M35 fixed, loading/error/destructive-action
UX, and the auth flow end to end. Strictly iOS-scoped (main app only, no
Share Extension, Web, or backend changes). Three parallel read-only audits
were explicitly instructed to skip everything M35 already fixed and
surface only genuinely new findings.

## Genuine Bugs Found & Fixed

### 1. Multi-day trip editing could silently corrupt/delete other days (data-loss risk)

The single biggest finding this milestone. `TripDetailView`'s `isEditing`
flag was only ever set `true` by the "Düzenle" toggle and **never reset
anywhere else**. `TripDetailViewModel.persistDay` — by design — only
reads/writes `trip.days.first` (Trip Builder trips start single-day, so
this was originally correct), overwriting `trip.days` with a single day
and PUTting only that one day's stop IDs to the server.

Failure scenario: on a single-day trip, the user opens "Düzenle" (the
toggle button is legitimately visible then, since `canEditStops =
!hasMultipleDays`). Without turning it off, they navigate to the
Optimizer or Apply History (both toolbar links stay reachable while
editing) and apply/undo into a multi-day state. Back on `TripDetailView`,
`hasMultipleDays` becomes `true` and the "Düzenle/Bitti" toggle
**disappears** — but `isEditing` is still `true`, so every stop across
*every* day still renders with move/delete controls. Deleting or
reordering any stop at that point triggers `persistDay`, which collapses
`trip.days` to a single day and sends only that day to the server —
**deleting the other day(s) both locally and on the backend.**

Fixed with a single `.onChange(of: vm.trip?.days.count)` on
`TripDetailView` that forces `isEditing = false` whenever the trip's day
count changes to more than one — making the corrupted state structurally
unreachable, without touching `TripDetailViewModel`'s existing (correct,
for its single-day assumption) persistence logic.

### 2. Stale map/list day selection could hide a non-empty stop list

The same `.onChange` handler above also reconciles `selection.dayIndex`:
if the trip's day structure changes (e.g. an undo collapses a multi-day
trip back to one day while "2. Gün" was selected), `visibleDays` filtered
against the now-invalid `dayIndex` produced an **empty array** — the
stops list visually vanished under a "Duraklar (N)" header that still
showed the correct non-zero count. Self-recoverable (tapping a map pin
reset the selection) but confusing. Fixed by falling back `dayIndex` to
`nil` ("Tümü") whenever it no longer matches any day in the reloaded trip.

### 3. Register screen's password-length hint didn't match the server's actual rule

`RegisterViewModel.canSubmit` required only 6 characters (and the field
hint said "min. 6 karakter"); the backend's real, shared rule (register
*and* reset-password — `ResetPasswordViewModel` already correctly used
8) requires **8**. A 6–7 character password passed client validation, the
button enabled, and the request deterministically failed server-side with
a generic "Gönderilen bilgiler eksik veya hatalı." that doesn't even
mention length. Fixed by raising the client rule and hint to 8, matching
the server.

### 4. A failed plan deletion replaced the entire Home trip list with a full-screen error

`HomeViewModel.deletePlan` reused the same `error` property `load()` uses.
`HomeView`'s body checks `vm.error` *before* `vm.plans.isEmpty`/the list,
so a single failed swipe-delete (e.g. a transient network blip) made the
**entire trip list disappear**, replaced by a full-screen "Sunucuya
ulaşılamıyor…" view with a "Tekrar Dene" that just reloads the list (not
the delete). Fixed by giving `deletePlan` its own `deleteError` property,
shown via a dedicated `.alert` — the same pattern already used by
`ItineraryHistoryView`/`ItineraryApplyHistoryView`/`TripDetailView` for
their own delete/undo failures — so the list now stays in place.

### 5. Trip deletion failures were completely silent

`TripDetailViewModel.deleteTrip` already exposed `deleteError`/`isDeleting`
(mirroring `stopEditError`, which *is* wired to an alert), but neither was
ever referenced in `TripDetailView`. A failed delete (network/server
error) produced zero feedback — no alert, and the trash button stayed
enabled, so a user could reopen the confirmation and silently no-op a
second attempt while the first was in flight. Fixed by wiring a
`deleteError` alert (matching `stopEditError`'s exact pattern) and
disabling/spinner-swapping the trash toolbar button while `isDeleting`.

### 6. Password-reset's "Giriş sayfasına dön" button didn't return to Login

`ResetPasswordView` is only ever reached via `LoginView → ForgotPasswordView
→ ResetPasswordView`, all pushed on the same stack. After a successful
reset, the button labeled "Giriş sayfasına dön" (Return to login) called
`dismiss()`, which — correctly per `NavigationStack` semantics — pops
exactly **one** level, landing back on `ForgotPasswordView`'s "check your
inbox" confirmation screen, not Login. Fixed with the standard SwiftUI
"pop N levels" pattern: `ForgotPasswordView` now passes `ResetPasswordView`
an `onFinished: { dismiss() }` closure (capturing *its own* `dismiss`);
the button calls that instead of its own `dismiss()`, correctly closing
both screens in one tap. No `NavigationStack` architecture change.

### 7. Apple Sign-In cancellation was shown as a hard failure

Canceling the native Apple Sign-In sheet produces `.failure(ASAuthorizationError.canceled)`.
`AuthEnvironment.appleSignIn` had no case for this — it fell through to
the generic `APPLE_AUTH_FAILED` → "Apple ile giriş başarısız." message,
alarming for what is normal, expected cancellation. Inconsistent with
Google's own button on the same screen, which already handles
`.cancelled` gracefully ("Google girişi iptal edildi."). Fixed by
detecting `ASAuthorizationError.canceled` explicitly and returning a
matching "Apple girişi iptal edildi." message before ever reaching the
network.

### 8. `ResultsView` had no empty state when all locations were deleted

Deleting every location via the edit UI (or an analysis that found zero
locations) left the "Keşfedilen Mekanlar" section completely blank — no
icon, no explanation — unlike `TripDetailView`'s own near-identical
stop-editor, which already has `emptyStopsState` for the exact same
scenario. Fixed by adding the equivalent `emptyLocationsState`, same
visual language, no new pattern invented.

## Accessibility Fixes

- `TripDetailView`'s four remaining toolbar icons (AI Assistant, Optimize,
  Optimization History, Apply History) got `accessibilityLabel`s — only
  the trash/delete icon had one after M35.
- `TripOptimizerConfigView`'s duration −/+ buttons got labels ("Gün
  sayısını azalt/artır") — the same class of icon-only-button gap M35 fixed
  for `LocationCard`, missed here.
- Five loading-state submit buttons (Login, Register, Forgot Password,
  Reset Password, Optimizer "Trip'e Uygula") swapped their `Text` for a
  bare `ProgressView` while loading with no accessible label left behind;
  all five now carry an explicit `accessibilityLabel` reflecting the
  loading state.
- Eight bare full-screen/inline `ProgressView`s (Home, Trip List, Trip
  Detail, Itinerary History, Apply History, Results, Library ×2) had no
  VoiceOver "loading" signal at all; all got `accessibilityLabel("Yükleniyor")`
  (or a more specific label where applicable, e.g. "Rota oluşturuluyor").
- `HomeView`'s upload-progress ring and `ProcessingView`'s
  `CircularProgressView` never exposed completion percentage to
  VoiceOver (and the upload ring didn't show it visually either — no
  percent text existed anywhere for it). Both now use
  `accessibilityElement(children:)` + `accessibilityLabel` +
  `accessibilityValue` — this project's first use of `accessibilityValue`,
  used exactly where semantically warranted (a progress percentage).

## Minor Fix

`APIError.unknown(statusCode:)`'s message read "Beklenmeyen hata (HTTP
0)." whenever a ViewModel's generic catch-all set `statusCode: 0` as a
meaningless placeholder (i.e. for a non-`APIError` Swift exception, not a
real HTTP response) — a raw, nonsensical technical detail leaking into
user-facing error text. Fixed the message to only show a real HTTP code
when one exists (`code > 0`); otherwise a plain "Beklenmeyen bir hata
oluştu." No call sites changed.

## Findings Reviewed and Deliberately Left Untouched

- **Optimizer caches (`OptimizerRouteCache`/`OptimizerSelectionStore`/
  `OptimizerConfigurationStore`) surviving `logout()`**: flagged as a
  theoretical cross-account collision risk if a different user's trip/
  itinerary IDs happened to match cached entries from a prior session.
  Investigated further than the initial audit: `OptimizerRouteCache` is
  keyed by geographic leg coordinates (collision requires identical
  coordinates — negligible), and both `OptimizerSelectionStore` and
  `OptimizerConfigurationStore` already validate/reconcile their cached
  value against the *live* trip/itinerary data on every read (documented
  as handling "the itinerary changed between visits" — the same
  validation path also catches "this cached entry belongs to a different
  itinerary entirely"). Given this existing defense-in-depth, and that a
  correct fix would require adding a new dependency direction (wiring
  `RootView` or `AuthEnvironment` to clear three sibling stores) for a
  risk that's already substantially mitigated, this was **not** fixed.
  Left as a documented candidate for a future multi-account/session-
  isolation audit if that ever becomes a real product requirement.
- **401 during a background/secondary action triggers an abrupt,
  unexplained full-app reset to `WelcomeView`**: confirmed real and
  consistent (every `handleUnauthorized()` call site behaves the same
  way) — but fixing it properly means introducing a "session expired"
  toast/banner, a UI primitive that doesn't exist anywhere in this app
  today. That's a new feature, not a bug fix or a small polish item, so
  it was left for a dedicated future decision rather than invented here.
- **"Tekrar Dene" on a 404 just retries the same doomed request**
  (deleted trip/itinerary/video): the error message itself is already
  correctly translated and non-technical, and a working back button is
  always available via the navigation bar, so this is a minor
  polish item, not a broken/blank screen. Left as a documented, low-
  priority finding.
- Everything the M35 doc already covers (day-chip selection-clearing
  precedent conflict, swipe-vs-context-menu gesture discrepancy, the one
  `?? fallback` stylistic gap) — re-confirmed still correctly out of
  scope, not re-litigated.
- The pre-existing, codebase-wide `apiError.localizedDescription ?? "…"`
  compiler warning (dead code — `.localizedDescription` is non-optional
  for any `LocalizedError`) appears at every call site across the app,
  not just the few files this milestone's diff touches. Per the
  milestone's own instruction not to fix unrelated pre-existing warnings,
  none of these were touched.

## Testing

13 new/modified tests added (395/395 passing, run twice for determinism):

- `RegisterViewModelTests` (+2): the exact 7-vs-8 character boundary that
  motivated fix #3.
- `AuthEnvironmentTests` (+1): Apple Sign-In cancellation regression
  (fix #7), asserting the distinct `APPLE_AUTH_CANCELLED` code/message and
  that zero network calls are made.
- `HomeViewModelTests.swift` (new, this ViewModel had zero prior
  coverage): initial state, successful delete, and the fix #4 regression
  (`deletePlan` failure restores the list and sets `deleteError`, never
  `error`).
- `TripDetailViewModelTests.swift` (new, this ViewModel had zero prior
  coverage): `deleteTrip`'s success/failure/unauthorized/re-entrancy
  contract — the VM-side half of fix #5 (the View-side alert wiring
  itself isn't reachable from this project's XCTest target, same
  limitation noted throughout this document).

**Limitation, same as M35**: fixes #1, #2, #6, and the empty-state/
accessibility-label additions are pure SwiftUI view/navigation changes
with no unit-test surface in this project (no UI test target exists).
These were verified by code review, by the fact they reuse already-tested
underlying contracts (`OptimizerSelection`'s `Equatable` conformance,
`deleteItinerary`'s `Bool` return, etc.), and by a full, deterministic
build + test pass — not by driving the actual navigation interactively.

## Real Simulator Verification

`xcodegen generate` → simulator build → device SDK build → full
`xcodebuild test`, all clean, on a real booted simulator (not just a
theoretical build target). No interactive UI automation tooling is
available in this environment (confirmed again this milestone), so per
Section 15's own instruction, no claim is made of an interactive
multi-screen walkthrough (Login → Forgot Password → Trip List → Trip
Detail → Optimizer → Assistant → confirmation dialogs). What *was* done:
the full deterministic test suite (the primary source of behavioral
confidence for this kind of change) and two clean full builds.

## Remaining Limitations

- No UI test target exists in this project — several of this milestone's
  fixes (navigation, dismiss chaining, alert wiring) are structurally
  correct by code review and by the underlying VM tests, but not directly
  exercised by an automated UI-level test.
- The "session expired" UX gap (no explanatory toast before the 401 →
  full-app-reset) and the optimizer-cache-survives-logout risk are both
  documented, real, but intentionally unfixed — see above for why.
- Dynamic Type support is a systemic, pre-existing gap across the entire
  app (every text style uses a hardcoded `.font(.system(size:))`, not a
  scalable text style) — far too broad to address as part of a "polish"
  milestone without it becoming a visual redesign, which this milestone's
  own instructions explicitly prohibit. Documented here for visibility,
  not fixed.

---

# Milestone 37 — End-to-End Product Flow Audit

A perspective shift from "is this screen correct?" (M25–M36) to "can a
real user complete the entire journey?" Three parallel audits traced
complete multi-screen flows — first-time auth, upload/processing → Home,
Trip Detail's full lifecycle, the complete optimizer chain, history/undo,
the assistant conversation, logout/session-expiration, and a dedicated
dead-end/data-integrity pass — each explicitly briefed on the full list of
M35/M36 fixes so they searched only for genuinely new *composition* bugs:
failures that only exist when two or more screens/ViewModels interact,
not defects visible from any single screen in isolation.

## Flows Audited

Flow A (first-time auth: register/login/forgot-password/reset/Google),
Flow B (upload → Processing → Home), Flow C (Trip Detail's full mutation
lifecycle), Flow D (the complete Optimizer chain: config → generate →
result → apply → back), Flow E (History & Undo, including the "latest
apply is the only undoable one" server-trust rule), Flow F (Assistant
conversation across reference-chip round trips), Flow G (logout/session
expiration across every authenticated screen), a dedicated dead-end
sweep, and a data-integrity spot-check (stale local state vs. server
truth).

## Already Correct (confirmed by tracing, not assumed)

- Flow A works end to end: registration auto-logs-in via `persist()` →
  `RootView` switches to `Home`; the M36-fixed Login-return chain from
  Reset Password is still correct; no form permanently locks up after an
  error in any of the four auth ViewModels.
- Upload duplicate-submission is correctly prevented (`PhotosPicker`
  disabled while `uploadState.isActive`); processing timeout lands on a
  real, actionable screen, not a dead end; Home reflects a newly
  completed plan immediately via `showResults(for:)`'s in-place `navPath`
  swap.
- `.viewSaved` itinerary history genuinely loads the saved result
  directly, never re-runs optimization.
- `isUndoable` is trusted verbatim from the server (never recomputed
  client-side) — directly proven by an existing test
  (`test_load_onlyLatestEntry_isMarkedUndoable`) covering exactly the
  "Apply A, Apply B, only B is undoable" scenario this milestone asked to
  verify.
- Undo never optimistically patches local state — it always reloads from
  the server before notifying the parent; the applied-itinerary banner
  has exactly one write site (the API-driven `TripDetailViewModel.load()`
  response), so it can never show stale content.
- The assistant's full multi-turn conversation (not just "preserved but
  hidden") survives a reference-chip → Trip Detail → reopen-Assistant
  round trip — directly proven by existing tests
  (`test_followUpQuestion_sendsPriorTurnAsHistory`,
  `test_multiTurnConversation_preservesFullOrderingInMessages`).
  `TripAssistantView`'s `trip:` parameter is re-passed fresh on every
  `TripDetailView.body` evaluation, so it can never go stale relative to
  a reload triggered from a screen below it in the stack.
- `RootView`'s binary `isAuthenticated` switch is a single point of
  truth: every authenticated screen lives inside one `NavigationStack`
  rooted at `HomeView`, so `handleUnauthorized()` atomically tears down
  the entire authenticated graph with no dangling stale UI, no crash risk
  from an orphaned ViewModel.
- No dead ends found anywhere: `ResetPasswordView` on an expired token
  stays editable with a link back to request a new one;
  `TripOptimizerView`'s "Kapat" button is unconditional regardless of
  error state; `ItineraryHistoryView`/`ItineraryApplyHistoryView`/
  `TripAssistantView` all keep the system back button available and pair
  every error with a working retry.
- `persistDay`'s optimistic-update-with-restore-on-failure is sound: a
  reordered/deleted stop either sticks (success) or visibly restores with
  an alert (failure) — it can never silently "snap back" unexplained.

## Genuine Issues Found & Fixed

### 1. `TripDetailView` blanked to a full-screen spinner on *every* reload, not just the first load

`if vm.isLoading { ProgressView() } ... else if let trip = vm.trip { tripContent(trip) }`
had no `vm.trip == nil` guard on the loading/error branches — unlike
every sibling list screen (`TripsListView`, `LibraryView`, `HomeView`,
all of which gate on `isLoading && collection.isEmpty`). Since `vm.load()`
is what every mutation callback (optimizer apply, itinerary delete, undo)
re-triggers, landing back on `TripDetailView` after **any** of those
actions tore down the already-rendered map/stop-list/scroll-position and
rebuilt it from a blank spinner — a real, visible flicker at exactly the
moment (right after "Trip'e Uygula") the user most wants a smooth
transition. Fixed by adding the same `vm.trip == nil` guard the sibling
screens already use, to both the loading and error branches.

### 2. `TripDetailView` had no pull-to-refresh

Every sibling list/detail screen (`TripsListView`, `LibraryView`,
`HomeView`) has `.refreshable`; `TripDetailView` — arguably the screen
most exposed to going stale, since optimizer/history/apply-history
mutations all touch it — had none. Fixed by adding `.refreshable`
matching the sibling pattern, refreshing the trip and both history flags.

### 3. A stale reference-chip could make Trip Detail's stop list appear to vanish

The assistant's reference chip carries a `(dayIndex, placeId)` pair
captured at the time the answer was generated. Because the assistant's
conversation (and thus its chips) now correctly survives long-lived
navigation (the M35 fix), that `dayIndex` can go stale if the trip's day
structure changes *while the conversation is still open* (e.g. an
apply/undo run from another screen collapses a 2-day trip to 1 day).
Tapping the now-stale chip set `selection.dayIndex` to a day that no
longer exists; `visibleDays` (filtered by `dayIndex`) then produced an
empty array while the "Duraklar (N)" header still showed the correct
non-zero count — the stops section appeared to have silently lost every
row. Self-recoverable (tapping any map pin resets the selection from
live data) but a real, reachable inconsistency. Fixed by re-deriving the
day index from the *stop's own current data* in the live `trip` (the
same principle `selectStop` already uses for map/list taps) instead of
trusting the chip's captured value; falls back to "Tümü" (nil) if the
stop no longer exists at all.

### 4. Home's video-upload 401 never triggered logout

`uploadVideoFile` deliberately bypasses `APIClient.send`'s refresh-retry
wrapper (uploads can run up to 600s; retrying a multi-MB body on a
stale token isn't worth it, so the pre-flight `validAccessToken()` check
exists instead) — but if the session became invalid *during* the upload
itself, the `catch {}` in `HomeView.handlePickedItem` was a bare,
generic catch that never checked `isUnauthorized`, unlike every other
authenticated call site in the app. The user saw a generic upload-failure
banner and remained nominally "logged in" (stale client-side state) until
their next unrelated action happened to hit a real 401. Fixed by adding
an `APIError.unauthorized`-specific catch that calls
`auth.handleUnauthorized()`.

### 5. Two "best-effort" background calls on `preloaded:`-opened screens silently swallowed 401s

`TripDetailViewModel.refreshItineraryHistoryFlag`/`refreshApplyHistoryFlag`
and `ResultsViewModel`'s travel-tips polling loop all end in a bare
`catch { /* best-effort */ }`, deliberately silent for their *normal*
failure mode (a transient network hiccup shouldn't hide a toolbar icon
loudly). But `TripDetailView(tripID:preloaded:)` (reached via
`LibraryView` right after "Gezi Oluştur") and `ResultsView(planID:
preloadedPlan:)` (reached via `HistoryView`) both skip `load()`'s own
network call entirely on that fast path — making these best-effort calls
the *only* live request against the server for a while. If the session
had genuinely expired by then, the app never found out: no logout, no
`RootView` transition, just a fully-interactive screen quietly holding
stale-relative-to-server state. Fixed by adding an `isUnauthorized` check
before the generic swallow in all three call sites — matching the
pattern (check-then-swallow-only-if-not-401) already used everywhere
else in the app, without touching the intentional silent behavior for
any *other* kind of error.

### 6. `ProcessingView` could freeze forever with no error/CTA in a rare token-refresh edge case

`ProcessingViewModel.fetchProgress()`'s 401 handler (added in M35)
cancels its polling/elapsed-time tasks but, unlike every other terminal
transition in the same file, never set `stage` to a terminal value. In
the common case this is invisible — `AuthEnvironment`'s own refresh
failure already triggered `handleUnauthorized()` before this code runs,
so `RootView` has already swapped the whole screen away. But if
`APIClient.send`'s refresh *succeeds* (new token persisted) and the
immediately-retried request *still* comes back 401 — a narrow but real
edge case the retry wrapper doesn't loop or re-invoke logout for — none
of that applies, and the screen was previously left frozen indefinitely
mid-stage: tasks cancelled, no error shown, no way forward. Fixed by
always setting `stage = .failed(message:)` in this handler, which
already renders a real message + a working "Geri Dön" button regardless
of which of the two scenarios actually occurred.

## Findings Reviewed and Deliberately Left Untouched

- Everything M35/M36 already reviewed-and-deferred (session-expired
  toast, optimizer-cache-survives-logout, 404-retry-repeats, Dynamic
  Type) — re-confirmed still correctly out of scope, not re-litigated.
- The `NavigationLink`-double-tap risk on "Optimize Et" flagged as
  *NEEDS MORE EVIDENCE* by this milestone's own audit: `TripOptimizerViewModel.run`'s
  re-entrancy guard is scoped to a single VM instance, and
  `TripOptimizerConfigView` creates a fresh VM per push, so a genuine
  SwiftUI-level double-push (if even possible) could theoretically bypass
  it. Whether `NavigationStack` can actually be double-triggered this way
  is a platform-timing question outside what static code reading or this
  project's XCTest target can confirm or deny — left undone rather than
  guessing at a fix for an unconfirmed problem.
- The pre-existing, codebase-wide `apiError.localizedDescription ?? "…"`
  dead-code warning — re-confirmed present but out of scope (none of this
  milestone's diffs touch those specific lines).

## Testing

4 new tests added (399/399 passing, run twice for determinism):

- `TripDetailViewModelTests` (+3): `refreshItineraryHistoryFlag`/
  `refreshApplyHistoryFlag` now correctly call `handleUnauthorized()` on
  a 401 and correctly do *not* on any other error (fix #5's VM-side
  contract).
- `ProcessingViewModelTests` (+1): 401 now always produces a terminal
  `.failed` stage (fix #6).

**Not unit-tested, verified by code review only:**
- Fixes #1–#3 are pure SwiftUI view-rendering/navigation logic (a
  conditional-branch guard, a `.refreshable` modifier, a closure's
  day-index derivation) with no unit-test surface in this project (no UI
  test target exists) — same limitation noted throughout M35/M36.
- Fix #4 (Home's upload 401) lives inside a private `HomeView` method
  driven by ad-hoc `@State`, not a testable ViewModel.
- `ResultsViewModel`'s tips-polling fix (part of #5) was **not** given a
  dedicated test: the poll loop's 3-second interval
  (`tipsPollInterval: Duration = .seconds(3)`) isn't currently injectable,
  and adding dependency injection *just* to make this one fix testable
  would be a disproportionately large change for a ~10-line catch-block
  fix. The underlying pattern (check `isUnauthorized` before swallowing)
  is already covered by the `TripDetailViewModel` tests above, which
  share the identical logic shape.

## Real Simulator Verification

`xcodegen generate` → simulator build → device SDK build → full
`xcodebuild test` (399/399, twice), all clean — same real, booted
simulator used throughout M35–M37. Installed, launched, and
screenshotted the app post-changes: `WelcomeView` renders correctly, no
crash on launch. No interactive UI-automation tooling is available in
this environment, so — consistent with every prior milestone in this
series — no claim is made of an interactive multi-screen walkthrough
(Login → Home → Trip Detail → Optimizer → Assistant → History → Apply
History → Logout). What *was* verified is the full deterministic test
suite (which is what most of this milestone's fixes actually depend on
for confidence) plus the two clean builds and the launch screenshot.

## Remaining Limitations

- Same "no UI test target" limitation as every prior milestone in this
  series — several of this milestone's fixes are structurally correct by
  code review and by adjacent VM-level tests, not by a driven UI test.
- The narrow `ProcessingViewModel` edge case (fix #6) could not be
  triggered end-to-end in a live environment (it depends on a specific
  server-side timing condition around token refresh) — the test added
  proves the *handler's* correctness given that input, not that the
  input is reachable in practice; the fix is a safety net for a scenario
  the code's own structure makes theoretically possible.
- `ResultsViewModel`'s tips-polling 401 fix has no dedicated test, for
  the reasons stated above.
