# iOS — AI Trip Optimizer

The iOS UI for the [AI Trip Optimizer](trip-optimizer.md), consuming the
[Mobile BFF proxy](trip-optimizer-bff.md) exclusively. Lets a user
generate a preview itinerary from an existing Trip Builder trip's stops,
and revisit any previously generated one — never mutates the trip itself.

Four milestones so far:
- **v1 — Generate & preview**: "Optimize Trip" entry point on
  `TripDetailView`, a fresh itinerary generated and shown in
  `TripOptimizerView`.
- **v2 — Itinerary History**: a second entry point, "Optimization
  History", lists every itinerary ever generated for a trip; selecting
  one reopens the same `TripOptimizerView` presentation loaded from the
  saved record — the optimizer is never re-run.
- **v3 — Apply to Trip**: an explicit "Trip'e Uygula" action, available
  in both `.generate` and `.viewSaved` modes, that copies the displayed
  itinerary's stops into the Trip's canonical `TripStop` list — the
  first (and still only) action in this feature that intentionally
  mutates the Trip. See "Apply to Trip" below.
- **v4 — User Controls for Place Selection and Trip Duration** (this
  update): a new `TripOptimizerConfigView` sits between `TripDetailView`
  and `TripOptimizerView`'s `.generate` mode — the user picks which of
  the trip's stops to optimize and (optionally) how many days the
  itinerary should span, *before* the optimize request goes out. See
  "Optimizer Configuration" below.

## Screen flow

```
TripDetailView (existing)
  │
  │  toolbar "sparkles" — only shown when trip.allStops is non-empty
  │  NavigationLink(destination: TripOptimizerConfigView(tripID:, stops:))
  │
  │  toolbar "clock.arrow.circlepath" — only shown when vm.hasItineraryHistory
  │  NavigationLink(destination: ItineraryHistoryView(tripID:))
  ▼                                          ▼
TripOptimizerConfigView              ItineraryHistoryView
  │  places list (default: all       │  loading/error/empty/list — TripsListView's
  │  selected), selected count,      │  exact 4-branch pattern
  │  duration stepper (default:      │
  │  Otomatik/nil)                   │  each row: NavigationLink(destination:
  │                                  │    TripOptimizerView(mode: .viewSaved(itineraryID:),
  │  "Optimize Et" — disabled        │                       onApplied: onApplied))
  │  when selection is empty         ▼
  ▼                                TripOptimizerView
TripOptimizerView                  (.viewSaved mode)
(.generate mode)                     │  .task { loads saved detail — never re-optimizes }
  │  .task { auto-optimizes with     │
  │  the config screen's selected    ├─ loading → "İtinerary yükleniyor…"
  │  placeIDs + durationDays }       ├─ error   → retry (e.g. deleted itinerary → 404)
  │                                  ├─ empty
  ├─ loading → "Gezi optimize        └─ success → same OptimizerScoreBadge/
  │            ediliyor…"                         ItineraryWarningsSection/
  ├─ error   → retry                              ItineraryDaySection as .generate,
  ├─ empty                                         "Trip'e Uygula" (NO "Daha Sonra
  └─ success → "Trip'e Uygula" +                   İçin Kaydet" — nothing new to save)
     footer "Daha Sonra İçin
     Kaydet"

  Both modes, whenever a non-empty result is shown:
    "Trip'e Uygula" → .confirmationDialog ("mevcut durak listesi değiştirilecek")
       → Uygula → vm.applyToTrip() → success alert → onApplied?() → dismiss()
                                    → failure alert bound to vm.applyError (recoverable, dialog stays reachable)

  toolbar leading "Kapat" — always available, in every state, dismisses immediately
```

Critically, **`ItineraryHistoryView` never routes through
`TripOptimizerConfigView`** — its `NavigationLink` still goes straight to
`TripOptimizerView(mode: .viewSaved(itineraryID:))`, byte-for-byte
unchanged by this milestone (the file wasn't touched at all). Opening a
saved itinerary always loads it directly; the configuration screen only
ever appears on the `.generate` (fresh-optimization) path.

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

## Optimizer Configuration

Before this milestone, tapping "sparkles" immediately ran the optimizer
against *all* of the trip's stops, with `duration_days` never sent (the
backend always self-derived the day count). `TripOptimizerConfigView` +
`TripOptimizerConfigViewModel` insert an explicit configuration step
between that tap and the actual optimize request — the user decides which
places to include and how many days to target, then taps "Optimize Et" to
actually run it.

### Design: reuse loaded data, no new network call

`TripOptimizerConfigView` takes `stops: [TripStop]` directly from
`TripDetailView`'s already-loaded `TripDetail` (`trip.allStops`) — it does
**not** issue its own fetch. Selection is pure, local, synchronous UI
state; nothing about it touches the network until "Optimize Et" is
tapped. This is deliberate: place selection is optimizer *input*, never a
`TripStop` mutation (selecting/deselecting a place in this screen never
calls `updateTripStopOrder` or any other Trip Builder endpoint — the
canonical stop list is completely unaffected regardless of what the user
selects or how the optimize request turns out).

### Default behavior preserves the pre-v4 behavior exactly

- **Selection**: `TripOptimizerConfigViewModel.init` seeds
  `selectedPlaceIDs` with *every* stop's `placeId` — if the user never
  touches the places list, the resulting `selected_place_ids` is
  identical to what `.generate` always sent before this milestone.
- **Duration**: `durationDays` starts at `nil` ("Otomatik") — if the user
  never touches the stepper, `duration_days` is omitted from the request
  entirely, exactly as before (the backend self-derives the day count,
  unchanged).

Both defaults mean a user who taps "sparkles" → "Optimize Et" without
touching anything gets **byte-identical behavior** to the pre-v4 flow —
this milestone is additive, not a behavior change for anyone who doesn't
use the new controls.

### Place selection UI

Mirrors `LibraryView`'s existing Trip-Builder multi-select pattern exactly
(same `Set<Int>` model, same `checkmark.circle.fill`/`circle` row
indicator pair, same card/border styling) — `TripStopSelectionRow` is a
`TripStop`-flavored sibling of `LibraryRowView`, not a new visual
language. Each row shows the place's name plus its category chip and city
(the same "enough context to distinguish places" fields `TripStop` already
carries — no new API field was needed). A header button toggles "Tümünü
Seç" / "Seçimi Kaldır" for convenience; a bottom-pinned bar (styled like
`LibraryView`'s own `selectionBar`) shows the live selected count and the
"Optimize Et" CTA.

### Duration control

A custom `-`/`+` stepper (not the native SwiftUI `Stepper`, to match this
app's own pill/circle button styling used everywhere else) cycles through
`Otomatik → 1 → 2 → … → 30 → (capped)`. `30` is a **UI-only** sensible
cap — `OptimizationService` only enforces `duration_days >= 1` server-side
(see `docs/trip-optimizer.md`), no upper bound exists there, so `30` is
this screen's own judgment call about a reasonable maximum, not a
mirrored backend constraint. Decrementing below `1` returns to `Otomatik`
(`nil`) rather than `0` or a negative number — the stepper structurally
cannot produce an invalid value.

### Validation

| Case | Handling |
|---|---|
| Zero places selected | `canOptimize` is `false`; "Optimize Et" is `.disabled(true)` and visibly dims; the count label switches to a destructive-colored "En az bir mekan seçmelisin" |
| Exactly one place selected | Allowed — `canOptimize` only requires non-empty, not `count >= 2` |
| Duration below/above the UI bounds | Structurally prevented — the stepper clamps at the source, see above |
| Backend validation errors (e.g. an unowned place ID, invalid `duration_days`) | Never reachable from this screen in practice (selection is always a subset of the trip's own already-owned stops, duration is always `nil` or a clamped valid int) — if the backend ever *did* reject the request, `TripOptimizerView`'s existing error state (unchanged) surfaces it with retry, same as any other optimize failure |
| Deleted/missing places | Impossible to select a place that isn't in `stops` — the list is exactly `trip.allStops` at screen-open time; a place deleted *after* the config screen opens but *before* "Optimize Et" is tapped would surface as a normal backend `INVALID_OPTIMIZATION_REQUEST` on submit, handled by `TripOptimizerView`'s existing error state |
| Permission errors, general optimization failure | Unchanged — still `TripOptimizerViewModel.optimize`'s existing error handling (401 → logout, other errors → `vm.error` with retry) |

Client-side validation only ever prevents the *obviously* invalid
zero-selection case, per the spec's own "prefer client-side validation
for obvious UI errors, but keep backend validation authoritative" —
everything else still round-trips to the same backend checks that already
existed.

### Request construction

"Optimize Et" is a plain `NavigationLink` into the existing
`TripOptimizerView(mode: .generate(tripID:placeIDs:durationDays:))` —
`placeIDs` comes from `selectedPlaceIDsInTripOrder` (the selected subset,
in the trip's own stop order — `Set` iteration order isn't deterministic,
so the view model filters the original ordered `stops` array instead of
enumerating the `Set` directly) and `durationDays` is passed through as-is
(`nil` when still "Otomatik"). `Endpoint.optimizeTrip` only adds
`duration_days` to the request body when non-nil — the wire format for
"Otomatize" is field omission, not `null`, matching how `duration_days`
already worked for every caller before this milestone.

No UI-only state (e.g. `isSelecting`-style mode flags, scroll position)
is ever sent — the request body contains exactly `selected_place_ids` and,
optionally, `duration_days`, nothing else new.

### Why `preferred_start_time`/`preferred_end_time` are still not exposed

Both fields already exist in the backend contract
(`OptimizeTripRequest.preferred_start_time`/`preferred_end_time`, default
`"09:00"`/`"18:00"`) and were inspected as part of this milestone's own
"before implementing" requirement. They are **deliberately left
unexposed** in iOS: this milestone's stated goal is place selection and
day count specifically ("Give the user explicit control over which
places are optimized and how many days"), and a full time-of-day control
pair is a third, materially different kind of input (two `HH:MM` pickers,
`end > start` client validation, a UI slot in an already-two-section
config screen) — exposing it well would meaningfully expand this
milestone's scope rather than "fit naturally" into it, which the spec's
own requirement 3 explicitly permits leaving alone. Flagged as a
candidate for a focused future milestone (see "Future UI improvements").

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

    func optimize(tripID: Int, placeIDs: [Int], durationDays: Int? = nil, auth: AuthEnvironment) async {
        await run(auth: auth) { token in
            try await auth.apiClient.send(
                .optimizeTrip(tripID: tripID, placeIDs: placeIDs, durationDays: durationDays), token: token
            )
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

### `TripOptimizerConfigViewModel`

Deliberately has **no** `AuthEnvironment`/network dependency at all — see
"Optimizer Configuration" above for why (selection is pure local state,
never a network call):

```swift
@Observable
@MainActor
final class TripOptimizerConfigViewModel {
    static let durationRange = 1...30   // UI-only cap, no backend upper bound exists

    let stops: [TripStop]
    private(set) var selectedPlaceIDs: Set<Int>
    private(set) var durationDays: Int?   // nil = Otomatik

    init(stops: [TripStop]) {
        self.stops = stops
        self.selectedPlaceIDs = Set(stops.map(\.placeId))   // default: ALL selected
    }

    var selectedCount: Int { selectedPlaceIDs.count }
    var canOptimize: Bool { !selectedPlaceIDs.isEmpty }     // zero-selection guard

    func toggle(_ placeID: Int) { /* insert/remove from the Set */ }
    func selectAll() { selectedPlaceIDs = Set(stops.map(\.placeId)) }
    func deselectAll() { selectedPlaceIDs.removeAll() }

    func incrementDuration() {
        durationDays = min((durationDays ?? 0) + 1, Self.durationRange.upperBound)
    }
    func decrementDuration() {
        guard let current = durationDays else { return }   // already Otomatik
        durationDays = current > Self.durationRange.lowerBound ? current - 1 : nil
    }

    var selectedPlaceIDsInTripOrder: [Int] {
        stops.map(\.placeId).filter(selectedPlaceIDs.contains)
    }
}
```

`selectedPlaceIDsInTripOrder` — not a raw `Array(selectedPlaceIDs)` —
exists because `Set` iteration order is not guaranteed stable/matching
insertion order; filtering the original, already-ordered `stops` array by
Set membership gives a deterministic request payload that mirrors the
trip's own canonical stop order, which is easier to reason about in both
manual testing and the test suite's own assertions.

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
| `.optimizeTrip(tripID:placeIDs:durationDays:)` | `/api/mobile/trips/{id}/optimize` | POST |
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

`durationDays` (new this milestone — see "Optimizer Configuration") is
the only field `TripOptimizerConfigView` actually controls at the wire
level: `Endpoint.body` adds `duration_days` to the JSON payload only when
non-nil, so "Otomatik" still means *field omitted entirely*, not
`"duration_days": null`. `start_date`/`preferred_start_time`/
`preferred_end_time`/`strategy` are still intentionally omitted —
core-api's own `OptimizeTripRequest` defaults apply (09:00–18:00,
`greedy_distance`); see "Optimizer Configuration → Why
preferred_start_time/preferred_end_time are still not exposed" for why
duration got a control this milestone but time-of-day didn't.

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

### No backend or BFF change for this milestone (v4)

`selected_place_ids` and `duration_days` already existed, field-for-field
identical, in core-api's `OptimizeTripRequest`, the mobile-bff's own
`OptimizeTripRequest` mirror, and the web-bff's — all the way back to the
optimizer's very first backend milestone. `TripOptimizerConfigView` only
had to start *sending* a value iOS was already capable of sending; per
the spec's own "only modify core-api if the existing endpoint cannot
correctly support the new UI behavior" / "only modify the BFF if the API
contract changes," neither applied here, and neither was touched.

### Backend change from the Itinerary History milestone (v2)

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
- **`TripStopSelectionRow`** (new, v4) — a `TripStop`-flavored sibling of
  `LibraryRowView`'s own selection-mode row: identical
  `checkmark.circle.fill`/`circle` indicator pair, identical
  card/border/corner-radius recipe, so a user who's already used Trip
  Builder's own multi-select (Library → "Gezi Oluştur") sees the exact
  same visual language here. Shows the stop's name, category chip, and
  city — reuses fields `TripStop` already carries, no new API field
  needed for "enough context to distinguish places."

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

64 tests, five files:

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
- **`TripOptimizerViewModelTests.swift`** (26 tests) — the original 10
  `optimize()` tests (initial state, success, server/network errors, a
  401 logs the session out *without* setting `error`, no-token
  short-circuit, deterministic loading-state + re-entrancy via
  `AsyncGate`) plus 5 `loadItinerary()` tests: fetches and populates
  the saved itinerary, **calls only `.itineraryDetail`, never
  `.optimizeTrip`** (the test that directly proves "selecting history
  never triggers a new optimization request"), server error, 401, and
  no-token — plus 10 `applyToTrip()` tests: initial state, success
  (forwards `.applyItinerary(itineraryID:)` + the bearer token, clears
  `isApplying`), **the displayed `vm.itinerary` stays byte-for-byte
  unchanged after a successful apply** (the test that directly proves
  "apply never mutates the preview"), server error, network error, a 401
  logs out *without* setting `applyError`, no-token short-circuit,
  deterministic `isApplying` via `AsyncGate`, a re-entrancy guard (second
  call while the first is in flight returns `false` immediately, API
  called only once), and repeated application succeeding twice in a row
  (mirrors core-api's own "can be applied repeatedly" guarantee) — plus
  **1 new test this milestone**, `test_optimize_forwardsDurationDays_
  whenProvided`, confirming `optimize(... durationDays: 4 ...)` reaches
  `.optimizeTrip` with that exact value (the existing forwarding test was
  also updated to assert `durationDays` is `nil` when the caller omits it).
- **`ItineraryHistoryViewModelTests.swift`** (10 tests) — initial
  state; `load()` happy path with an assertion on the exact endpoint
  called (`.itineraries(tripID:)`); **newest-first ordering**, both as a
  pure unit test directly against `sortedNewestFirst` (no networking at
  all) and as an integration test feeding `load()` a deliberately
  out-of-order server response to confirm the screen doesn't just trust
  it; **empty history** (empty array in, empty array out, no error);
  **API failure** (network error and a `TRIP_NOT_FOUND` server error,
  both asserted against `vm.error`); 401 handling; no-token guard;
  re-entrancy guard (same `AsyncGate` pattern as the optimizer VM). Fully
  unchanged by this milestone — direct evidence that the saved-itinerary
  path (`.viewSaved`, reached only through this screen's own rows) never
  touches the new configuration screen or its ViewModel.
- **`OptimizerEndpointTests.swift`** (11 tests) — networking tests, pure
  and synchronous: `Endpoint.urlRequest` path/method/body/`Authorization`
  header, plus JSON-decoding tests against realistic server payloads.
  **2 new this milestone**: `duration_days` is omitted from the body when
  `nil` (the default — byte-identical to every pre-v4 request), and
  included with the exact value when provided.
- **`TripOptimizerConfigViewModelTests.swift`** (17 tests, new) — pure
  local state, no `FakeAPIClient` involved at all (this ViewModel makes
  no network calls — see "Optimizer Configuration"): default selection is
  every stop; default duration is Otomatik (`nil`); an empty `stops` array
  produces an empty, non-optimizable selection; toggling
  deselects/reselects correctly; `selectAll`/`deselectAll`; selected count
  reflects partial selections; `canOptimize` is `false` only at exactly
  zero selected (confirmed `true` at exactly one); duration increment from
  Otomatik lands on `1`, stops exactly at the `30`-day upper bound even
  after many extra increments; duration decrement from `1` returns to
  Otomatik, and decrementing while already at Otomatik is a no-op (never
  produces `0` or negative); a 100-call increment/decrement stress test
  confirming the value never leaves `[1, 30]` or `nil`; and
  `selectedPlaceIDsInTripOrder` preserving the trip's own stop order
  regardless of selection/toggle order (not `Set` iteration order), both
  for a full selection and a partial one.

### Test results

```
Test Suite 'All tests' passed
Executed 64 tests, with 0 failures (0 unexpected) in 0.073-0.105s
```

Verified stable across 5 repeated full-suite `xcodebuild test` runs (not
just once) — same discipline established as necessary since the
project's first flaky-test discovery. Full `xcodebuild build` also
verified clean, no new warnings. This milestone made **no core-api,
mobile-bff, or web-bff changes** (see "API integration → No backend or
BFF change for this milestone"), so no backend/BFF suite reruns were
required — the counts from the previous (Apply to Trip / OR-Tools)
milestones stand unchanged.

A live Simulator launch-and-crash-free check was performed (install →
launch → screenshot of the initial screen) to confirm the rebuilt app
runs; a full interactive tap-through of the new configuration screen
was **not** performed — this environment has no XCUITest/accessibility
automation harness for the iOS Simulator (unlike, say, a browser
automation tool for web UIs), so that level of verification relies on the
64 passing automated tests plus the clean build instead.

## Assumptions / limitations (v2 — Itinerary History)

- No date/duration/time-window picker — always uses core-api's defaults.
  (Historical note: duration got its own control in v4, "User Controls
  for Place Selection and Trip Duration," below; date/time-window are
  still unaddressed — see "Assumptions / limitations (v4)".)
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

## Assumptions / limitations (v4 — User Controls)

- **`preferred_start_time`/`preferred_end_time` still aren't exposed** —
  deliberately, this milestone's own scope decision; see "Optimizer
  Configuration → Why preferred_start_time/preferred_end_time are still
  not exposed" above.
- **`30` days is a UI-only cap**, not a mirrored backend constraint —
  `OptimizationService` only enforces `duration_days >= 1`, no upper
  bound. If a real trip ever needed more than 30 days, the backend would
  happily accept it; only this screen's stepper would need its constant
  raised.
- **No persistence of the user's selection/duration choice** —
  `TripOptimizerConfigViewModel` is created fresh (all stops selected,
  Otomatik duration) every time the config screen is opened; there's no
  "remember my last configuration" behavior. Consistent with every other
  screen in this feature (nothing here has ever persisted UI-only state
  across sessions).
- **No "select by category/city" bulk filter** — only individual toggle
  and "Tümünü Seç"/"Seçimi Kaldır" exist; for a trip with many stops
  across several cities, a per-city bulk toggle could be a reasonable
  future refinement once real usage shows it's needed.

## Future UI improvements

Ranked by what unlocks the most value next:

1. **`preferred_start_time`/`preferred_end_time` controls** — expose the
   remaining constraint core-api already accepts but this milestone
   deliberately left alone (see "Optimizer Configuration" above for why).
   The natural next increment now that place selection and duration exist.
2. **Map view of the optimized route** — `TripMapView` already exists and
   accepts a route polyline (used by `TripDetailView`); reusing it here to
   visualize the optimized order geographically is a low-effort addition.
3. **Delete a history entry** — needs a new core-api `DELETE
   /internal/itineraries/{id}` (+ BFF proxy) first; today history is
   append-only.
4. **Apply history / undo** — `Trip.applied_itinerary_id` only tracks the
   most recently applied itinerary; there's no way to see or revert to an
   earlier apply. Would need a core-api apply-history table first (see
   `docs/trip-optimizer.md` "Future improvements").
5. **Web UI** — web-bff already exposes the full owner/editor surface
   including `apply` (parity with mobile-bff), but no web page calls any
   of it yet; every iOS-only milestone so far, including this one, has
   left it unaddressed.
6. **Bulk selection by category/city** — see "Assumptions / limitations
   (v4)" above.
