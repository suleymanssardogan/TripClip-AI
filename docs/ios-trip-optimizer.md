# iOS — AI Trip Optimizer

The iOS UI for the [AI Trip Optimizer](trip-optimizer.md), consuming the
[Mobile BFF proxy](trip-optimizer-bff.md) exclusively. Lets a user
generate a preview itinerary from an existing Trip Builder trip's stops,
and revisit any previously generated one — never mutates the trip itself.

Three milestones so far:
- **v1 — Generate & preview**: "Optimize Trip" entry point on
  `TripDetailView`, a fresh itinerary generated and shown in
  `TripOptimizerView`.
- **v2 — Itinerary History**: a second entry point, "Optimization
  History", lists every itinerary ever generated for a trip; selecting
  one reopens the same `TripOptimizerView` presentation loaded from the
  saved record — the optimizer is never re-run.
- **v3 — Apply to Trip** (this update): an explicit "Trip'e Uygula"
  action, available in both `.generate` and `.viewSaved` modes, that
  copies the displayed itinerary's stops into the Trip's canonical
  `TripStop` list — the first (and still only) action in this feature
  that intentionally mutates the Trip. See "Apply to Trip" below.

## Screen flow

```
TripDetailView (existing)
  │
  │  toolbar "sparkles" — only shown when trip.allStops is non-empty
  │  NavigationLink(destination: TripOptimizerView(mode: .generate(tripID:, placeIDs:)))
  │
  │  toolbar "clock.arrow.circlepath" — only shown when vm.hasItineraryHistory
  │  NavigationLink(destination: ItineraryHistoryView(tripID:))
  ▼                                          ▼
TripOptimizerView                    ItineraryHistoryView
(.generate mode)                     │  loading/error/empty/list — TripsListView's
  │  .task { auto-optimizes }        │  exact 4-branch pattern
  │                                  │
  ├─ loading → "Gezi optimize        │  each row: NavigationLink(destination:
  │            ediliyor…"            │    TripOptimizerView(mode: .viewSaved(itineraryID:),
  ├─ error   → retry                 │                       onApplied: onApplied))
  ├─ empty                           ▼
  └─ success → "Trip'e Uygula" +   TripOptimizerView
     footer "Daha Sonra İçin      (.viewSaved mode)
     Kaydet"                        │  .task { loads saved detail — never re-optimizes }
                                     │
                                     ├─ loading → "İtinerary yükleniyor…"
                                     ├─ error   → retry (e.g. deleted itinerary → 404)
                                     ├─ empty
                                     └─ success → same OptimizerScoreBadge/
                                                  ItineraryWarningsSection/
                                                  ItineraryDaySection as .generate,
                                                  "Trip'e Uygula" (NO "Daha Sonra
                                                  İçin Kaydet" — nothing new to save)

  Both modes, whenever a non-empty result is shown:
    "Trip'e Uygula" → .confirmationDialog ("mevcut durak listesi değiştirilecek")
       → Uygula → vm.applyToTrip() → success alert → onApplied?() → dismiss()
                                    → failure alert bound to vm.applyError (recoverable, dialog stays reachable)

  toolbar leading "Kapat" — always available, in every state, dismisses immediately
```

`onApplied` is threaded from `TripDetailView` through both paths to
`TripOptimizerView` — directly for `.generate`, through
`ItineraryHistoryView`'s own `onApplied` passthrough parameter for
`.viewSaved` — so a successful apply from *either* entry point refreshes
`TripDetailViewModel.trip` in the background (see "Apply to Trip" below).

`TripOptimizerView`/`ItineraryHistoryView` never appear in Trip Builder's
own flow unmodified — both are new destinations reached from new,
conditionally-shown toolbar buttons. `TripDetailView`'s existing
map/stats/stop-list/edit/delete code is untouched; the one addition to
`TripDetailViewModel` is a second, independent, best-effort method (see
"Itinerary History" below) — `load()` itself is unmodified.

### Why "Close" and "Save for later" do the same thing server-side

Requirement: *"the generated itinerary is only a preview... do NOT modify
the user's Trip automatically... provide Close, Save for later, no Apply
action yet."* Core-api's `optimize_trip` **already persists** the itinerary
unconditionally the moment it succeeds (see `docs/trip-optimizer.md`
"Architecture" — every run creates a standalone `TripItinerary` row,
independent of `TripStop`). There's no "discard" endpoint and nothing to
opt out of — by the time this screen shows a result, it's already saved.

So both buttons produce the identical server-side outcome; they differ
only in what the user is told:
- **Kapat** (toolbar, always visible): dismiss immediately, no message.
- **Daha Sonra İçin Kaydet** (footer, only once there's a real result):
  shows a confirmation alert ("saved, the trip itself didn't change, you
  can view it again later") before dismissing.

This is a deliberate, honest design choice, not a shortcut — inventing a
fake "discard" behavior would be worse than not having one, since nothing
on the backend actually supports it.

**Now that Itinerary History exists**, `.viewSaved` mode (opened from a
history row) hides the "Daha Sonra İçin Kaydet" footer button entirely
rather than showing a redundant "save" for something that's already,
definitionally, history — it was saved the moment it was generated. Only
`.generate` mode (a fresh run) shows it.

**"Trip'e Uygula" (Apply to Trip) is the one deliberate exception** to
"nothing here mutates the Trip" — see the next section. Unlike Close/Save,
which are both no-ops server-side, Apply is a real, explicit, confirmed
mutation.

## Apply to Trip

The only action anywhere in this feature that intentionally changes the
Trip's canonical `TripStop` list (see `docs/trip-optimizer.md` "Apply
semantics" for the full backend contract, atomicity, and safety
guarantees). Shown as a "Trip'e Uygula" button whenever a non-empty
itinerary result is displayed — in **both** `.generate` and `.viewSaved`
modes, since both show a fully-formed, applicable itinerary; there's
nothing mode-specific about which itineraries are eligible.

Flow, entirely within `TripOptimizerView`:

1. Tap "Trip'e Uygula" → `.confirmationDialog` explains the current Trip
   stop list will be replaced (mirrors `TripDetailView`'s own delete
   confirmation pattern — same `.confirmationDialog` + `titleVisibility:
   .visible` recipe).
2. Confirm → `vm.applyToTrip(itineraryID:auth:)` — the button shows a
   `ProgressView` in place of its label while `vm.isApplying` is true, and
   is `.disabled` for the same duration (double-submission is additionally
   guarded inside the ViewModel itself, not just the button state — see
   below).
3. Success → a confirmation `.alert` ("durak listesi güncellendi"); tapping
   "Tamam" calls `onApplied?()` then `dismiss()`.
4. Failure → a separate `.alert` bound to `vm.applyError` (the same
   `Binding(get:set:)`-clears-on-dismiss pattern `TripDetailView` uses for
   `stopEditError`) — recoverable: the screen stays exactly as it was, the
   user can retry the same button.

No auto-apply: applying only ever happens from this explicit, confirmed
button tap — never as a side effect of generating or loading an itinerary
(`optimize`/`loadItinerary` are completely unchanged by this milestone).

### Refreshing `TripDetailView` after a successful apply

`TripOptimizerView` takes an optional `var onApplied: (() -> Void)? = nil`.
`TripDetailView` wires it, for its own `.generate` `NavigationLink`, to
`{ Task { await vm.load(tripID: tripID, auth: auth) } }` — reloading the
trip (now showing the newly-applied stops) the moment the success alert is
dismissed. `ItineraryHistoryView` gained the same `onApplied` parameter,
purely as a passthrough to its own `.viewSaved` `NavigationLink`, so a
`.viewSaved` apply — reached one level deeper in the nav stack — refreshes
`TripDetailViewModel` the same way. Since `TripDetailView` stays alive on
the navigation stack the whole time (SwiftUI never deallocates a pushed
view until it's popped), calling `vm.load` in the background works even
before the user has navigated back to it — by the time `TripDetailView`
is visible again, `vm.trip` already reflects the applied stops.

### Why the saved itinerary and displayed preview are untouched

Applying reads the itinerary and writes to the trip — it never writes to
the itinerary. `vm.itinerary` (what `TripOptimizerView` renders) is not
reassigned anywhere in `applyToTrip`; a test
(`test_applyToTrip_success_doesNotMutateDisplayedItinerary`) asserts the
displayed itinerary is byte-for-byte identical before and after a
successful apply. Reopening the same itinerary from Itinerary History
afterward still shows the original result — matching core-api's own
guarantee (see `docs/trip-optimizer.md`).

## ViewModel

### `TripOptimizerViewModel`

Now has **two** public entry points sharing one private `run` helper — the
try/catch/401-handling logic lives in exactly one place, not duplicated
between "generate new" and "load saved":

```swift
@Observable
@MainActor
final class TripOptimizerViewModel {
    private(set) var itinerary: Itinerary?
    private(set) var isLoading = false
    private(set) var error: APIError?

    func optimize(tripID: Int, placeIDs: [Int], auth: AuthEnvironment) async {
        await run(auth: auth) { token in
            try await auth.apiClient.send(.optimizeTrip(tripID: tripID, placeIDs: placeIDs), token: token)
        }
    }

    func loadItinerary(itineraryID: Int, auth: AuthEnvironment) async {
        await run(auth: auth) { token in
            try await auth.apiClient.send(.itineraryDetail(itineraryID: itineraryID), token: token)
        }
    }

    private func run(auth: AuthEnvironment, request: (String) async throws -> Itinerary) async {
        guard !isLoading else { return }        // re-entrancy guard
        isLoading = true; error = nil
        defer { isLoading = false }

        guard let token = auth.user?.token else { return }

        do {
            itinerary = try await request(token)
        } catch let apiError as APIError {
            if apiError.isUnauthorized { auth.handleUnauthorized(); return }
            error = apiError
        } catch {
            self.error = .unknown(statusCode: 0)
        }
    }

    // Apply to Trip — independent isApplying/applyError pair, deliberately
    // NOT sharing `run`'s isLoading/error: applying is a different action
    // than loading, can happen after a load already completed, and must
    // never be confused with it in the UI.
    private(set) var isApplying = false
    var applyError: String?

    @discardableResult
    func applyToTrip(itineraryID: Int, auth: AuthEnvironment) async -> Bool {
        guard !isApplying, let token = auth.user?.token else { return false }
        isApplying = true; applyError = nil
        defer { isApplying = false }

        do {
            let _: ApplyItineraryResult = try await auth.apiClient.send(
                .applyItinerary(itineraryID: itineraryID), token: token
            )
            return true
        } catch let apiError as APIError {
            if apiError.isUnauthorized { auth.handleUnauthorized(); return false }
            applyError = apiError.localizedDescription
            return false
        } catch {
            applyError = "Itinerary uygulanamadı."
            return false
        }
    }
}
```

`applyToTrip` follows `TripDetailViewModel.deleteTrip`'s exact shape
(`@discardableResult ... -> Bool`, `guard !isApplying` re-entrancy, a
plain mutable `var applyError: String?` rather than `private(set)` — same
precedent as `stopEditError`/`deleteError`, since the View needs to clear
it on alert dismissal) rather than `optimize`/`loadItinerary`'s shared
`run` helper — applying isn't a "fetch and populate `itinerary`" operation,
it's a fire-and-report-success/failure one, so forcing it through `run`
would have meant either misusing `isLoading` for an unrelated action or
adding awkward branches to a helper built for a different shape.

`loadItinerary` calls `GET /itineraries/{id}` — it **never** calls
`POST /trips/{id}/optimize`. Selecting a row in Itinerary History cannot,
by construction, trigger a new optimization run; there is no code path
from `.viewSaved` mode to the `optimize` endpoint at all.

No separate "empty" flag: `TripOptimizerView` derives the empty state
itself from `itinerary.days.flatMap(\.stops).isEmpty` — the ViewModel just
carries whatever the server returned, same division of responsibility as
every other screen (e.g. `LibraryView` deriving its own empty/no-results
states from `vm.places`, not a VM-owned enum).

### `ItineraryHistoryViewModel`

Structurally identical to `TripsListViewModel.load` (the closest existing
list-screen analog):

```swift
@Observable
@MainActor
final class ItineraryHistoryViewModel {
    private(set) var itineraries: [ItinerarySummary] = []
    private(set) var isLoading = false
    private(set) var error: APIError?

    func load(tripID: Int, auth: AuthEnvironment) async {
        guard !isLoading else { return }
        isLoading = true; error = nil
        defer { isLoading = false }

        guard let token = auth.user?.token else { return }

        do {
            let response: ItineraryListResponse = try await auth.apiClient.send(
                .itineraries(tripID: tripID), token: token
            )
            itineraries = Self.sortedNewestFirst(response.itineraries)
        } catch let apiError as APIError {
            if apiError.isUnauthorized { auth.handleUnauthorized(); return }
            error = apiError
        } catch {
            self.error = .unknown(statusCode: 0)
        }
    }

    static func sortedNewestFirst(_ items: [ItinerarySummary]) -> [ItinerarySummary] {
        items.sorted { a, b in
            guard let dateA = a.createdAt.flatMap(APIDate.parse),
                  let dateB = b.createdAt.flatMap(APIDate.parse) else { return false }
            return dateA > dateB
        }
    }
}
```

`sortedNewestFirst` is a `static func`, deliberately — it's a pure
function, directly unit-testable without any networking mock. core-api's
`list_itineraries` already returns `created_at DESC` (see
`docs/trip-optimizer-bff.md`), so this is a defensive second sort, not the
primary source of ordering — if the server contract ever changed, the
screen would still show newest-first.

### `TripDetailViewModel`

Gained one new, independent, best-effort property + method — `load()`
itself is byte-for-byte unmodified:

```swift
private(set) var hasItineraryHistory = false

func refreshItineraryHistoryFlag(tripID: Int, auth: AuthEnvironment) async {
    guard let token = auth.user?.token else { return }
    do {
        let response: ItineraryListResponse = try await auth.apiClient.send(
            .itineraries(tripID: tripID), token: token
        )
        hasItineraryHistory = !response.itineraries.isEmpty
    } catch {
        // best-effort — the flag just stays false, no error surfaced
    }
}
```

`TripDetailView` runs this in a **second, parallel `.task`** alongside the
existing trip-load `.task` — both start on appear, neither blocks the
other. If this call fails, the "Optimization History" toolbar button
simply doesn't appear; the trip screen itself never shows an error for it
(same "non-critical supplementary data" precedent as the explore/landing
pages' `getStats()` handling).

## API integration

Routes only through the Mobile BFF (`http://<host>:8001/api/mobile/...`)
— **never** talks to core-api directly, per the requirement. Four
`Endpoint` cases (`Core/Network/Endpoint.swift`), following the exact
convention every other endpoint uses (central enum, not per-feature files):

| Case | Path | Method |
|---|---|---|
| `.optimizeTrip(tripID:placeIDs:)` | `/api/mobile/trips/{id}/optimize` | POST |
| `.itineraries(tripID:)` | `/api/mobile/trips/{id}/itineraries` | GET |
| `.itineraryDetail(itineraryID:)` | `/api/mobile/itineraries/{id}` | GET |
| `.applyItinerary(itineraryID:)` | `/api/mobile/itineraries/{id}/apply` | POST |

All four endpoints are in active use: `.optimizeTrip` from
`TripOptimizerView(.generate)`, `.itineraries` from both
`ItineraryHistoryView` (the list) and `TripDetailViewModel` (the
history-exists flag), `.itineraryDetail` from
`TripOptimizerView(.viewSaved)`, `.applyItinerary` from
`TripOptimizerViewModel.applyToTrip` (both modes — see "Apply to Trip").
`.applyItinerary` sends no body — it falls through to `Endpoint.body`'s
`default: return nil`, matching core-api's and both BFFs' own no-body
apply routes.

The `optimize` POST body intentionally omits `start_date`/`duration_days`/
`preferred_start_time`/`preferred_end_time`/`strategy` — core-api's own
`OptimizeTripRequest` defaults apply (09:00–18:00, `greedy_distance`).
There's no date/duration picker in this v1; see "Future UI improvements."

New Codable models (`Core/Models/OptimizerModels.swift`) mirror core-api's
`OptimizeTripResponse` field-for-field (`Itinerary`, `ItineraryDay`,
`ItineraryStop`, plus `ItinerarySummary`/`ItineraryListResponse` for the
list endpoint, plus `AppliedTripStop`/`ApplyItineraryResult` for the apply
response), decoded via `APIClient`'s existing `.convertFromSnakeCase` — no
custom `CodingKeys` needed anywhere.

`AppliedTripStop` deliberately uses `lat`/`lng` (matching `ItineraryStop`'s
naming), **not** `TripStop`'s `latitude`/`longitude` — because the mobile-bff
`apply` route, like the rest of `trip_optimization.py`, is a raw
pass-through with no field-renaming transformer (unlike `trips.py`'s
routes, which do rename `lat`/`lng` → `latitude`/`longitude` via
`trip_transformer.py`). See `docs/trip-optimizer-bff.md` "Request/response
contracts → apply" for the exact wire shape this mirrors.

### Backend change required for this milestone

`ItinerarySummary` (the list-endpoint DTO) originally had no way to know
how many days or stops an itinerary contained — those only existed in the
full-detail `days` array, which the list endpoint deliberately doesn't
return (that's the whole point of a summary). Since this milestone's own
requirement is to show day/stop counts in the history list, core-api's
`ItinerarySummaryResponse` and `SqlOptimizationRepository.list_itineraries`
were extended with `days_count`/`stops_count` — computed via two grouped
`COUNT`/`COUNT(DISTINCT day_index)` queries against `TripItineraryStop`,
batched across all of a trip's itineraries in one round trip each (no N+1).
This is additive and backward-compatible: existing consumers of the list
endpoint that don't know about the new fields are unaffected. See
`docs/trip-optimizer-bff.md` for the updated contract.

## UI components

New, in `Features/Trips/Components/` (mirrors the existing
`Features/Results/Components/` split — `TripOptimizerView` stays thin,
each visual concern gets its own file):

- **`OptimizerScoreBadge`** — score (color-coded: ≥80 success, 50–79
  warning, <50 destructive) + distance + travel time, in the same
  3-cell-divided-strip recipe as `TripDetailView.statsStrip`.
- **`ItineraryWarningsSection`** — warning-tinted card, visually separated
  from the itinerary (own background/border color, own section, per the
  explicit requirement), rendering core-api's warning strings verbatim.
- **`ItineraryDaySection`** — day header + time-prefixed stop rows
  (arrival time, name, visit duration, travel-time-to-next), producing
  exactly the requested layout:
  ```
  1. Gün
  09:00  Colosseum         30 dk ziyaret
  09:32  Roman Forum       30 dk ziyaret
  ```

No new design tokens were needed — `AppColors.warning` already existed
(unused elsewhere) specifically for this kind of cautionary UI.

- **`ItineraryHistoryRowView`** — one row in the history list. Copies
  `TripRowView`'s exact card recipe (leading 52×52 rounded-rect badge +
  two-line meta + trailing chevron) rather than inventing a new visual
  language; the one change is that the badge shows the itinerary's score
  number (color-coded, same three-tier logic as `OptimizerScoreBadge`)
  instead of an icon. Meta lines: days/stops count (`Label` + SF Symbol,
  matching `TripRowView`'s own `"\(trip.stopsCount) durak"` pattern),
  formatted creation date, and a warning-count `Label` (only shown when
  `warnings` is non-empty) in `AppColors.warning`.

## Itinerary History

### Entry point (`TripDetailView`)

A second toolbar button, `clock.arrow.circlepath`, positioned between the
existing "sparkles" (optimize) and "trash" (delete) buttons. Gated on
`vm.hasItineraryHistory` — **only shown once the trip actually has at
least one generated itinerary** (per the explicit requirement), populated
by the independent `refreshItineraryHistoryFlag` call described above.
Tapping it pushes `ItineraryHistoryView(tripID:)`.

### `ItineraryHistoryView`

Exact structural copy of `TripsListView`'s four-branch state pattern
(`vm.isLoading && vm.itineraries.isEmpty` → spinner; `vm.error,
vm.itineraries.isEmpty` → error+retry; `vm.itineraries.isEmpty` → empty
state; else → list), `.refreshable` pull-to-refresh included. Rows are
`NavigationLink(destination: TripOptimizerView(mode: .viewSaved(itineraryID:)))`
wrapped in `PressableButtonStyle()` — the same `NavigationLink` +
`ItineraryHistoryRowView` pairing `TripsListView` uses for
`NavigationLink(destination: TripDetailView(tripID:))` + `TripRowView`.

No new navigation mechanism: still plain `NavigationStack` push, same
single stack `HomeView` owns, same as every other screen in this feature
area.

### Non-destructive behavior (reaffirmed)

This milestone adds a *second way to reach* `TripOptimizerView`'s existing
result presentation — it does not add any new way to mutate a `Trip`:

- `ItineraryHistoryView` only ever performs `GET` requests
  (`.itineraries`, then `.itineraryDetail` when a row is tapped).
- `TripOptimizerView(.viewSaved)` calls `loadItinerary`, which calls
  `GET /itineraries/{id}` — never `POST /trips/{id}/optimize`. There is no
  code path from browsing history to generating a new optimization run.
- `TripStop` (Trip Builder's canonical stop list) is never read or
  written by *browsing* history, in either mode — `GET` requests only.
  Confirmed by the existing `test_optimize_does_not_mutate_existing_trip_stops`
  core-api test.
- The one exception, added in v3, is the explicit "Trip'e Uygula" button
  — an intentional, confirmed, user-initiated mutation, never a side
  effect of viewing or generating an itinerary. See "Apply to Trip" above
  for the full flow and its safeguards (confirmation dialog, no
  auto-apply, double-submission guard).

## Enabling change: completing the `APIClientProtocol` DI seam

There was no iOS test target before this work, and no ViewModel had ever
actually been tested — `APIClientProtocol` existed (for exactly this
purpose, per its own doc comment) but `AuthEnvironment.apiClient` was
typed as the concrete, `final` `APIClient` everywhere, so nothing could
ever inject a fake. Two small, behavior-preserving changes unlock it:

1. **`APIClientProtocol`** gained `uploadVideoFile(...)` (it only had
   `send<T>`) — the one non-protocol member any call site actually used
   (`HomeView`'s upload flow), found by grepping every `auth.apiClient.`
   call site before making the change.
2. **`AuthEnvironment.apiClient`** is now typed `APIClientProtocol`
   instead of `APIClient`; the concrete `refreshHandler` callback is
   wired conditionally (`if let concrete = apiClient as? APIClient`) so
   production behavior (default `APIClient()`) is byte-for-byte unchanged
   — a fake injected in tests just skips that wiring, since fakes don't
   need the 401-refresh-retry flow.
3. A `#if DEBUG`-only `AuthEnvironment.setUserForTesting(_:)` was added
   (same file, so it can reach the `private(set)` `user` setter) — the
   only way to get a test double past `AuthEnvironment.init`'s real
   `restoreSession()`/Keychain path without touching Keychain at all.

`ProcessingViewModel`/`ProcessingView` (the only other concrete-`APIClient`
call sites, found the same way) were widened to `APIClientProtocol` too,
for the same reason — otherwise `HomeView`'s existing
`ProcessingView(apiClient: auth.apiClient, ...)` call wouldn't compile
once `auth.apiClient`'s static type changed. Verified via a full
`xcodebuild build` (not just SourceKit) that nothing else broke.

## Testing

New target: `TripClipAppTests` (didn't exist before — added via
`project.yml` + `xcodegen generate`, since this project generates its
`.xcodeproj` from a declarative spec rather than hand-maintaining
`project.pbxproj`).

```bash
cd ios
xcodegen generate
xcodebuild -project TripClipApp.xcodeproj -scheme TripClipApp \
  -destination 'platform=iOS Simulator,name=iPhone 17 Pro' test
```

44 tests, four files:

- **`Support/FakeAPIClient.swift`** — `APIClientProtocol` test double.
  Returns a canned `Result<Any, Error>`; two independent `AsyncGate`s (a
  small `actor` wrapping a `CheckedContinuation`) give deterministic
  control over an in-flight call: `startedGate` opens the instant `send`
  is entered (before any `await`, same instant as `callCount` increments)
  so a test can `await started.wait()` for "the request has definitely
  begun" instead of guessing with `Task.yield()`; `gate` is what the test
  then holds closed to keep the call suspended mid-flight until it's
  done asserting. An earlier version used a fixed number of
  `Task.yield()` calls to approximate "the child task has started" —
  that passed the first several runs, then failed once under
  scheduler load (a genuinely flaky assertion, not a one-off fluke),
  which is why it was replaced with this explicit signal instead.
- **`TripOptimizerViewModelTests.swift`** (25 tests) — the original 10
  `optimize()` tests (initial state, success, server/network errors, a
  401 logs the session out *without* setting `error`, no-token
  short-circuit, deterministic loading-state + re-entrancy via
  `AsyncGate`) plus 5 `loadItinerary()` tests: fetches and populates
  the saved itinerary, **calls only `.itineraryDetail`, never
  `.optimizeTrip`** (the test that directly proves "selecting history
  never triggers a new optimization request"), server error, 401, and
  no-token — plus 10 new `applyToTrip()` tests: initial state, success
  (forwards `.applyItinerary(itineraryID:)` + the bearer token, clears
  `isApplying`), **the displayed `vm.itinerary` stays byte-for-byte
  unchanged after a successful apply** (the test that directly proves
  "apply never mutates the preview"), server error, network error, a 401
  logs out *without* setting `applyError`, no-token short-circuit,
  deterministic `isApplying` via `AsyncGate`, a re-entrancy guard (second
  call while the first is in flight returns `false` immediately, API
  called only once), and repeated application succeeding twice in a row
  (mirrors core-api's own "can be applied repeatedly" guarantee).
- **`ItineraryHistoryViewModelTests.swift`** (10 tests, new) — initial
  state; `load()` happy path with an assertion on the exact endpoint
  called (`.itineraries(tripID:)`); **newest-first ordering**, both as a
  pure unit test directly against `sortedNewestFirst` (no networking at
  all) and as an integration test feeding `load()` a deliberately
  out-of-order server response to confirm the screen doesn't just trust
  it; **empty history** (empty array in, empty array out, no error);
  **API failure** (network error and a `TRIP_NOT_FOUND` server error,
  both asserted against `vm.error`); 401 handling; no-token guard;
  re-entrancy guard (same `AsyncGate` pattern as the optimizer VM).
- **`OptimizerEndpointTests.swift`** (9 tests, unchanged from the prior
  milestone except one decoding test now also asserts `days_count`/
  `stops_count` decode correctly) — **networking tests**, pure and
  synchronous: `Endpoint.urlRequest` path/method/body/`Authorization`
  header for all three cases, plus JSON-decoding tests against realistic
  server payloads.

### Test results

```
Test Suite 'All tests' passed
Executed 44 tests, with 0 failures (0 unexpected) in 0.053-0.075s
```

Verified stable across 5 repeated full-suite `xcodebuild test` runs (not
just once) — same discipline the prior milestone's flaky-test discovery
established as necessary. Full `xcodebuild build` also verified clean, no
new warnings.

core-api's own suite grew by 14 tests for `apply_itinerary` (happy path,
owner, editor, viewer rejection, cross-user rejection, nonexistent
itinerary, deleted place, empty itinerary, duplicate places, atomic
rollback, repeated application, saved-itinerary-unchanged, provenance
fields, analytics event) — full core-api suite: 358 passed (was 344).
mobile-bff and web-bff each grew by 6 tests for the `apply` proxy route
(auth, forwarding, and 404/403/400/503 propagation) — 102 passed (was 96)
and 59 passed (was 53) respectively.

## Assumptions / limitations (v2 — Itinerary History)

- No date/duration/time-window picker — always uses core-api's defaults.
  A natural v3 addition once there's demand for it.
- No strategy picker — `greedy_distance` is the only strategy that exists
  server-side today anyway (see `docs/trip-optimizer.md`).
- No pagination on the history list — `GET /trips/{id}/itineraries`
  returns every itinerary ever generated for the trip in one response.
  Fine at today's scale (a user manually tapping "optimize" repeatedly);
  would need a `limit`/`offset` (core-api doesn't support this yet either)
  if history depth ever became large enough to matter.
- No way to delete a history entry — there's no `DELETE
  /itineraries/{id}` on core-api, so history only ever grows. Not
  addressed here; flagged as a possible future backend addition below.
- `refreshItineraryHistoryFlag`'s failure is silent by design (see
  "ViewModel" above) — if it fails, the toolbar button just doesn't
  appear even when history genuinely exists. Acceptable for a
  supplementary affordance; the history is never actually lost, just not
  advertised until the next successful check (e.g. next time the screen
  loads).
- The loading state's `ProgressView` doesn't rasterize correctly under
  `ImageRenderer`-based offline snapshotting (a tool limitation used only
  to produce this doc's screenshots, not a runtime issue — confirmed
  separately via a live Simulator launch, both in the prior milestone and
  again here via the real Mobile BFF, that the real spinner renders
  normally, same `ProgressView` code already shipping elsewhere in the app).

## Assumptions / limitations (v3 — Apply to Trip)

- **No visible diff before applying.** The confirmation dialog explains,
  in words, that the current stop list will be replaced, but doesn't show
  a before/after comparison of exactly which stops would change. Matches
  core-api's own v1 scope — a diff view would need new backend support to
  compute cheaply.
- **No apply-history UI** — only the single most-recent
  `applied_itinerary_id`/`itinerary_applied_at` pointer is ever shown (via
  `TripDetail`, exposed by `GET /trips/{id}` but not yet surfaced anywhere
  in `TripDetailView`'s own UI). See "Future UI improvements" below.
- **Apply is available from a saved itinerary's history row even if it's
  old** — there's no "this itinerary is outdated" warning if the trip's
  places have since changed (e.g. a place removed from the Library). This
  matches the backend's behavior: an apply against an itinerary containing
  a since-deleted place is rejected at apply time (`400`), not proactively
  flagged in the history list beforehand.

## Future UI improvements

Ranked by what unlocks the most value next:

1. **Date/duration/time-window controls** — expose the constraints
   core-api already accepts (`start_date`, `duration_days`,
   `preferred_start_time`/`preferred_end_time`) instead of always using
   its defaults.
2. **Place selection** — right now "Optimize Trip" always uses *all* of
   the trip's current stops; letting the user deselect a subset before
   generating (mirroring Library's own multi-select UI) is a reasonable
   next increment once the all-stops case has real usage.
3. **Map view of the optimized route** — `TripMapView` already exists and
   accepts a route polyline (used by `TripDetailView`); reusing it here to
   visualize the optimized order geographically is a low-effort addition.
4. **Delete a history entry** — needs a new core-api `DELETE
   /internal/itineraries/{id}` (+ BFF proxy) first; today history is
   append-only.
5. **Apply history / undo** — `Trip.applied_itinerary_id` only tracks the
   most recently applied itinerary; there's no way to see or revert to an
   earlier apply. Would need a core-api apply-history table first (see
   `docs/trip-optimizer.md` "Future improvements").
6. **Web UI** — web-bff already exposes the full owner/editor surface
   including `apply` (parity with mobile-bff), but no web page calls any
   of it yet; this milestone, like the two before it, is iOS-only.
