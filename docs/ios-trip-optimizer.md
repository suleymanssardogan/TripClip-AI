# iOS — AI Trip Optimizer

The iOS UI for the [AI Trip Optimizer](trip-optimizer.md), consuming the
[Mobile BFF proxy](trip-optimizer-bff.md) exclusively. Lets a user
generate a preview itinerary from an existing Trip Builder trip's stops,
and revisit any previously generated one — never mutates the trip itself.

Twenty milestones so far:
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
- **v4 — User Controls for Place Selection and Trip Duration**: a new
  `TripOptimizerConfigView` sits between `TripDetailView` and
  `TripOptimizerView`'s `.generate` mode — the user picks which of the
  trip's stops to optimize and (optionally) how many days the itinerary
  should span, *before* the optimize request goes out. See "Optimizer
  Configuration" below.
- **v5 — Optimized Route Map Visualization**: both `.generate` and
  `.viewSaved` results now render a map of the optimized stop order —
  day-separated, gracefully handling missing coordinates, reusing
  `TripOptimizerView`'s existing score/warnings/day-list/apply
  presentation unchanged. See "Map Visualization" below.
- **v6 — Real Road Route Visualization (MapKit Directions)**: the
  straight-line segments v5 drew between consecutive stops are now
  replaced, where possible, with real driving-route geometry from
  `MKDirections` — still day-separated, still falling back to a straight
  line per-segment when a route can't be calculated, still no external
  routing dependency. See "Real Road Route Visualization" below.
- **v7 — Bidirectional Itinerary ↔ Map Interaction**: the itinerary
  day/stop list and the route map, previously independent, now share one
  selection state — tapping a stop in the list focuses/centers it on the
  map, and tapping a marker on the map highlights and scrolls to the
  matching row in the list. See "Bidirectional Itinerary ↔ Map
  Interaction" below.
- **v8 — Preferred Start/End Time Controls**: the `TripOptimizerConfigView`
  gains two time pickers — the optimizer's existing `preferred_start_time`/
  `preferred_end_time` fields, already used server-side since the very
  first optimizer milestone but never before sent by iOS, are now real,
  user-editable, client-validated inputs that reach every generate
  request. See "Preferred Start/End Time Controls" below.
- **v9 — Trip Planning Date**: an optional third control, "Planlama
  Tarihi," lets the user anchor a generated itinerary to a real calendar
  date — day sections then show "12 Ağustos 2026" instead of a bare "1.
  Gün." Required a small, surgical core-api change (the backend already
  computed this value internally; it just never returned it) — the only
  backend change across this feature's entire history. See "Trip Planning
  Date" below.
- **v10 — Date-aware Map Day Selector**: the route map's day-selector
  chips (`OptimizerRouteMapSection`), until now always `"1. Gün"`/`"2.
  Gün"`, now show the same real calendar date v9 already surfaced
  elsewhere — `"12 Ağustos"` — whenever one exists, falling back to the
  ordinal label otherwise. A pure display change: day-selection identity,
  route caching, and camera behavior are all untouched. See "Date-aware
  Map Day Selector" below.
- **v11 — Persistent Optimizer Route Cache**: the driving
  routes `OptimizerRouteCalculator` computes via `MKDirections` now
  survive leaving and reopening the same itinerary — previously every
  fresh `TripOptimizerView` push recomputed every route from scratch, even
  for the exact same saved itinerary (a known limitation called out since
  v6). A new `OptimizerRouteCache`, owned at the app/session level (same
  DI pattern as `AuthEnvironment`), caches successful per-leg route
  geometry across screen visits. A pure performance change: no API
  semantics, request/response shapes, or on-screen behavior differ from
  v10 — a cache hit just skips the network call. See "Persistent Optimizer
  Route Cache" below.
- **v12 — Optimizer Route Transport Mode**: a compact
  Araba/Yürüyüş selector on the route map lets the user choose whether
  `MKDirections` calculates driving or walking route geometry — the
  optimizer's own stop *ordering* is completely unaffected, this is a
  route-*visualization* preference only. `OptimizerRouteCalculator` and
  `OptimizerRoutingProviding` gained a `mode` parameter (defaulting to
  `.automobile`, so every pre-v12 call site keeps its exact prior
  behavior), and v11's per-leg cache key gained a `mode=` component so
  driving and walking results for the same leg coexist independently
  rather than overwriting each other. See "Optimizer Route Transport
  Mode" below.
- **v13 — Persistent Optimizer Map Selection**: the day and
  stop the user had selected on the route map now survives leaving and
  reopening the same itinerary during the current app session — previously
  `OptimizerSelection` reset to "Tümü"/no-stop every time, even for the
  exact same itinerary reopened moments later. A new `OptimizerSelectionStore`,
  owned at the app/session level (same DI pattern as `OptimizerRouteCache`),
  stores the last-known selection keyed by `Itinerary.id` and validates it
  against the itinerary's *current* contents on every restore — an invalid
  day falls back to the first available day, a deleted stop falls back to
  its (still-valid) day, and everything degrades to the pre-existing
  default rather than ever crashing. See "Persistent Optimizer Map
  Selection" below.
- **v14 — Overnight Time Ranges**: the optimizer's planning
  window (`Planlama Saatleri` — Start/End) and a place's own opening hours
  can now cross midnight — `18:00 → 01:00`, `22:00 → 02:00` — end-to-end,
  from the backend's scheduling model through to iOS's own client-side
  validation. This is primarily a **backend** milestone (core-api's
  `GreedyDistanceStrategy`/`ORToolsRouteOptimizationStrategy` both gained a
  shared, continuous-timeline time-window representation); the iOS side is
  one line — `TripOptimizerConfigViewModel.isTimeRangeValid` now rejects
  only genuinely equal start/end values, not every `end < start` pair. No
  UI redesign, no new fields, no date/timezone arithmetic added on either
  side. See "Overnight Time Ranges" below.
- **v15 — Persistent Optimizer Configuration**: the entire
  optimizer configuration screen — selected places, duration, preferred
  start/end time, planning date, and (for the map's own later use)
  transport mode — now survives leaving and reopening the config screen
  for the same trip during the current app session. A new
  `OptimizerConfigurationStore`, owned at the app/session level (same DI
  pattern as `OptimizerRouteCache`/`OptimizerSelectionStore`), stores the
  last-known configuration keyed by `Trip.id` and reconciles it against
  the trip's *current* places on every restore — a removed place drops
  out, a newly-added one is never auto-selected, an invalid saved time
  range falls back to the existing defaults. See "Persistent Optimizer
  Configuration" below.
- **v16 — Persistent Optimizer Transport Mode Sync**: closes
  the one-directional gap left by v15 — until now, `OptimizerConfigurationStore`
  → `OptimizerRouteMapSection`'s `initialTransportMode` was the only
  direction data flowed; changing Araba/Yürüyüş directly on the route map
  never wrote back. `OptimizerRouteMapSection` gained an
  `onTransportModeChanged` callback (fired from its existing transport
  selector, alongside its own already-local `@State`) so `TripOptimizerView`
  can relay the change to `OptimizerConfigurationStore.updateTransportMode(_:for:fallbackSelectedPlaceIDs:)`
  — a new store method that updates just the `transportMode` field of an
  existing configuration, or creates one (seeded with the currently
  displayed itinerary's own place IDs, never an empty selection) if the
  config screen was never visited for that trip. The map still has no
  knowledge that `OptimizerConfigurationStore` exists. See "Persistent
  Optimizer Transport Mode Sync" below.
- **v17 — Optimizer Configuration Transport Mode Picker**:
  exposes the transport-mode value (persisted since v15, synced with the
  map since v16) through an actual control on `TripOptimizerConfigView`
  itself — a native segmented `Picker` (🚗 `car.fill` / 🚶 `figure.walk`)
  added below the existing planning-time card. No new state container:
  the picker reads/writes `TripOptimizerConfigViewModel.transportMode`
  exactly like the duration stepper reads/writes `durationDays`, which
  already persists through the existing `persistConfiguration()` →
  `OptimizerConfigurationStore` flow — the same store the map's own
  selector reads and writes since v16. See "Optimizer Configuration
  Transport Mode Picker" below.
- **v18 — Transit Transport Mode**: adds `.transit`
  (🚋 `tram.fill`, "Toplu Taşıma") as a third `OptimizerTransportMode`
  case. Because the entire transport-mode architecture (cache keying,
  routing-provider mapping, configuration persistence, both selector UIs)
  was already generic over `OptimizerTransportMode.allCases` rather than
  hardcoded to two cases, this milestone required **no structural
  changes** to `OptimizerRouteCalculator`, `OptimizerRouteCache`,
  `OptimizerConfiguration`, or `OptimizerConfigurationStore` — extending
  the enum alone made Transit a fully working, independently-cached,
  fully-persisted third mode everywhere those types are used. The only
  code changes were the enum case itself, `MKDirectionsRoutingProvider`
  mapping it to `MKDirectionsTransportType.transit`, wrapping the map's
  transport selector in a horizontal `ScrollView` (three chips no longer
  guaranteed to fit an unscrollable row), and documentation. Transit
  routing is availability-dependent (region/coverage/schedule) and reuses
  the existing straight-line fallback + non-caching-of-failures behavior
  that automobile/walking already had since v6. See "Transit Transport
  Mode" below.
- **v19 — Delete Saved Itinerary from History**: a saved
  itinerary can now be deleted from `ItineraryHistoryView` — swipe-to-delete
  on a row, a confirmation dialog, then a real backend `DELETE` request
  through the existing `iOS → Mobile BFF → Core API → PostgreSQL` chain
  (new core-api `DELETE /internal/itineraries/{id}`, a matching Mobile BFF
  and Web BFF proxy, and `Endpoint.deleteItinerary`/`ItineraryHistoryViewModel.deleteItinerary`
  on iOS). `TripStop`/`Place` are never touched; if the deleted itinerary
  was `Trip.applied_itinerary_id`, that reference is cleared instead of
  left dangling — a foreign key already declared with `ON DELETE SET NULL`
  specifically in anticipation of this milestone. Anti-enumeration is
  stricter here than the existing `apply` endpoint: both "doesn't exist"
  and "exists but you're not owner/editor" return the identical
  `404 ITINERARY_NOT_FOUND`. See "Delete Saved Itinerary" below.
- **v20 — Apply History & Undo** (this update): a new, durable
  `trip_itinerary_apply_history` table records every successful
  apply *and* undo as a uniform log entry — each carrying the complete
  `TripStop` snapshot from immediately before it, so any of them can, in
  principle, restore exactly what came before. Only the trip's single most
  recent entry may actually be undone (`409 STALE_UNDO` otherwise) — this
  prevents an old undo from silently clobbering a newer apply. A new
  `ItineraryApplyHistoryView`/`ItineraryApplyHistoryViewModel` (reachable
  from a new `TripDetailView` toolbar entry) lists the log and exposes
  "Geri Al" only on the one entry the server says is undoable — the
  restored state is never guessed client-side, the screen always reloads
  from the server after a successful undo. The saved `TripItinerary` is
  never written to by undo; deleting an itinerary never destroys the
  history that references it (only the FK clears, mirroring
  `Trip.applied_itinerary_id`'s own precedent). See "Apply History &
  Undo" below.

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
is ever sent — the request body contains exactly `selected_place_ids`,
`duration_days` (optionally), and — as of v8 — `preferred_start_time`/
`preferred_end_time` (always; see "Preferred Start/End Time Controls"
below).

### Why `preferred_start_time`/`preferred_end_time` are still not exposed — superseded by v8

> **Superseded by v8.** This subsection described the deliberate scope
> decision v4 made at the time. As of "Preferred Start/End Time Controls"
> below, both fields are now exposed, client-validated, real UI controls.
> Left intact below for historical accuracy about why v4 didn't include
> them.

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

## Preferred Start/End Time Controls

`TripOptimizerConfigView` gains a third section, `preferredTimeSection`,
alongside the existing place-selection and duration sections — two time
pickers exposing core-api's `OptimizeTripRequest.preferred_start_time`/
`preferred_end_time`. These fields have existed in the backend contract
since the optimizer's very first milestone and are actively used by
*both* `GreedyDistanceStrategy` and `ORToolsRouteOptimizationStrategy` to
derive each day's scheduling window (see `docs/trip-optimizer.md`
"Algorithm") — this milestone doesn't add new backend capability, it
exposes capability that already existed and was already exercised
server-side, just never reachable from iOS.

### Was a backend/BFF change necessary? No

Every piece of the contract this milestone needed already existed,
field-for-field, before any code was written:

- core-api `OptimizeTripRequest.preferred_start_time`/`preferred_end_time`
  (`str`, default `"09:00"`/`"18:00"`, validated as `"HH:MM"` with
  `end > start` required — see `OptimizationService._validate_hhmm`/the
  `preferred_end_time <= preferred_start_time` rejection).
- mobile-bff's own `OptimizeTripRequest` mirror (`trip_optimization.py`)
  — identical field names/types/defaults, pure pass-through
  (`body.model_dump()`), no transformation.
- Backend test coverage for both parameters was already adequate before
  this milestone: `test_trip_optimization.py` covers format/range
  validation at the route level; `test_optimization_strategy.py` uses
  non-default `preferred_start_time`/`preferred_end_time` values to prove
  the *day-splitting behavior itself* responds to them (not just accepts
  them). Per the spec's own "add the smallest necessary core-api test(s)
  only if coverage is insufficient" — it wasn't, so **no core-api, BFF, or
  test changes were made on the backend side at all.** This milestone is
  100% additive iOS work reusing an already-complete, already-tested
  contract.

### Architecture/design decision: extend, don't duplicate

Per the spec's own "if an existing configuration ViewModel already
exists, extend it instead of creating another independent state
container," the new state lives entirely inside the existing
`TripOptimizerConfigViewModel` — no second config object, no parallel
settings screen. The same pattern `durationDays`/`incrementDuration`/
`decrementDuration` established in v4 is followed exactly: `private(set)`
properties + explicit setter methods, never a raw public `var` the View
could mutate arbitrarily.

### `ClockTime`: a type-safe internal representation

Per the spec's "do not pass arbitrary display strings through the
application... convert to the API's expected representation only at the
network boundary," a new small value type,
`Core/Models/ClockTime.swift`, carries hour/minute through the entire
app — `TripOptimizerConfigViewModel`, `TripOptimizerViewModel`, and
`TripOptimizerView.Mode.generate` all pass `ClockTime` values, never raw
`"HH:MM"` strings:

```swift
struct ClockTime: Equatable, Comparable {
    var hour: Int
    var minute: Int

    static func < (lhs: ClockTime, rhs: ClockTime) -> Bool {
        (lhs.hour, lhs.minute) < (rhs.hour, rhs.minute)
    }

    var apiValue: String { String(format: "%02d:%02d", hour, minute) }
}
```

Deliberately **not** `Date` — a clock time has no date, no timezone, no
DST; modeling it as a bare `(hour, minute)` pair avoids importing
irrelevant complexity (which calendar day? which timezone?) that `Date`
would otherwise carry for no benefit. `apiValue` is the *only* place the
`"HH:MM"` string is produced, and it's called from exactly one place in
the whole app: `Endpoint.body`'s `.optimizeTrip` case — the literal
network boundary, right before `JSONSerialization.data(withJSONObject:)`.

Two static defaults mirror core-api's own exactly, byte-for-byte (Req 3
"the iOS UI should reflect those [backend] values," not an invented
default):

```swift
extension ClockTime {
    static let defaultStart = ClockTime(hour: 9, minute: 0)   // core-api: "09:00"
    static let defaultEnd   = ClockTime(hour: 18, minute: 0)  // core-api: "18:00"
}
```

A small bridge to `Date` exists *only* for `DatePicker` binding (SwiftUI
has no native "time-only" picker type) — `asDate`/`init(date:)` — and is
never used for anything else; comparison, validation, and encoding all
happen on `ClockTime` directly, never on the bridged `Date`.

### UI: two `DatePicker`s in the existing config screen

```
Planlama Saatleri
┌─────────────────────────────┐
│ Başlangıç Saati        09:00 │
├─────────────────────────────┤
│ Bitiş Saati             18:00 │
└─────────────────────────────┘
Optimizer günlük planı bu saat aralığına sığdırır.
Mekanların kendi açılış saatleri ayrıca dikkate alınır.
```

No custom control was built — the project had no prior `DatePicker` usage
anywhere to "reuse," so this milestone establishes the pattern using
SwiftUI's own native `DatePicker(selection:displayedComponents: .hourAndMinute)`
in its default (`.compact`) style, which already matches the spec's own
mockup (`"Start time" / "09:00"`, a label plus a tappable HH:MM value).
The section itself reuses the exact card recipe `durationSection`
established (`AppColors.surface` background, `AppColors.border` 1pt
stroke, 16pt corner radius, 16pt horizontal padding) — visually
indistinguishable in style from the duration control next to it, per Req
10's "keep the UI consistent with the rest of the app." The picker row is
wrapped in `.environment(\.locale, Locale(identifier: "tr_TR"))` so it
always renders 24-hour `"09:00"`-style time regardless of the device's
own region setting — the same locale-forcing precedent `APIDate.displayString`
already established for date formatting elsewhere in this app.

### Defaults (Req 3)

`TripOptimizerConfigViewModel.preferredStartTime`/`preferredEndTime`
initialize to `.defaultStart`/`.defaultEnd` (`09:00`/`18:00`) — a user who
opens the config screen and never touches the new pickers gets a request
byte-identical, field values included, to what core-api would have
defaulted to on its own. The only observable change for that user is that
the fields are now *explicitly present* in the request body rather than
omitted (see "Request wire format" below) — the resulting optimization
behavior is unchanged either way, since core-api's own default is the
value now being sent explicitly.

### Validation (Req 4) — superseded by v14

```swift
var isTimeRangeValid: Bool { preferredStartTime < preferredEndTime }
var canOptimize: Bool { !selectedPlaceIDs.isEmpty && isTimeRangeValid }
```

This was the ORIGINAL (v8) rule — `preferred_end_time` had to be
*strictly* after `preferred_start_time` (equal was rejected too, matching
`OptimizationService`'s `<=` check at the time, not `<`). **As of v14
("Overnight Time Ranges" below), `isTimeRangeValid` is `preferredStartTime
!= preferredEndTime`** — only equal values are still rejected; `end <
start` is now a valid overnight planning window, matching core-api's own
updated contract. `canOptimize` — the same property that already gated
the "Optimize Et" button on a non-empty place selection since v4 —
continues to gate on **both** conditions; no new disablement mechanism
was introduced. The bottom bar's message distinguishes which condition is
failing (`"En az bir mekan seçmelisin"` vs. a time-range message) rather
than a single generic "invalid" string, so the user always knows what to
fix without guessing.

**No auto-correction.** Changing the start time never touches the end
time and vice versa (`setPreferredStartTime`/`setPreferredEndTime` each
write exactly one property) — if that produces an invalid (equal) range,
the UI surfaces it and blocks "Optimize Et" rather than silently nudging
the other value. This was a deliberate choice, not an oversight: the same
"structural, not corrective" philosophy the duration stepper already
uses (it clamps at its own bounds rather than reaching into unrelated
state), and it's exactly what the spec's own test list requires
("changing only the start time doesn't modify the end time").

~~**Overnight ranges are out of scope**, per the spec's explicit
exclusion — `isTimeRangeValid` requires `start < end` within a single
day, with no wraparound. This isn't an arbitrary iOS-side restriction:
core-api's shared `_parse_opening_hours`... doesn't support
midnight-crossing ranges either...~~ **No longer true as of v14** — see
"Overnight Time Ranges" below for the full backend redesign that made
this possible.

### Request wire format (Req 1, Req 2, Req 5)

`Endpoint.optimizeTrip` gained two new associated values, both with
defaults matching core-api's own:

```swift
case optimizeTrip(
    tripID: Int, placeIDs: [Int], durationDays: Int? = nil,
    preferredStartTime: ClockTime = .defaultStart, preferredEndTime: ClockTime = .defaultEnd
)
```

**Unlike `duration_days`, these two fields are never omitted** —
`Endpoint.body`'s `.optimizeTrip` case now always includes both:

```swift
var body: [String: Any] = [
    "selected_place_ids":   placeIDs,
    "preferred_start_time": preferredStartTime.apiValue,
    "preferred_end_time":   preferredEndTime.apiValue,
]
if let durationDays { body["duration_days"] = durationDays }
```

This is a deliberate asymmetry, not an inconsistency: `duration_days` has
a genuine three-state UI (`Otomatik`/nil vs. a specific day count) where
field omission *is* the "Otomatik" signal to the backend. Preferred
start/end time have no such tri-state — the picker always shows a
concrete value, so there is nothing for field-omission to *mean*; always
sending the field is the only representation that matches what the user
actually sees on screen. This is also, mechanically, why v4's own
`test_optimizeTrip_bodyContainsSelectedPlaceIDs` test (previously
asserting the request body contained *only* `selected_place_ids`, i.e.
`json.count == 1`) was updated this milestone to `json.count == 3` — the
old assertion's own justifying comment ("preferred_*_time... kasıtlı
olarak gönderilmiyor") is no longer true, by design.

The full chain, each layer forwarding the same `ClockTime` values
unchanged: `TripOptimizerConfigView`'s pickers write through
`TripOptimizerConfigViewModel.setPreferredStartTime`/`setPreferredEndTime`
→ "Optimize Et" constructs `TripOptimizerView.Mode.generate(...,
preferredStartTime:, preferredEndTime:)` → `TripOptimizerView.load()`
forwards them to `TripOptimizerViewModel.optimize(...)` → which passes
them straight to `Endpoint.optimizeTrip(...)` → `.apiValue` converts to
`"HH:MM"` at the JSON boundary → mobile-bff passes the body through
unchanged → core-api's existing, already-tested validation and strategy
logic take over. No layer in this chain re-validates, re-formats, or
duplicates the time-range check beyond the one client-side
`isTimeRangeValid` gate — core-api's own validation remains the
authoritative check (Req 6 "the backend remains the source of truth").

### Opening hours interaction (Req 7)

Preferred start/end time and a place's own opening hours are — and
remain — two independent constraints that core-api combines; nothing
about this changes here, and iOS makes no attempt to reproduce the
combination logic:

```
User preferred window:  09:00 ──────────────────────── 18:00
Place opening hours:            10:00 ── 12:00
```

If the optimizer's schedule would arrive at that place before `10:00`,
the strategy waits (silently — see `docs/trip-optimizer.md` "Algorithm"
step 3); if it would arrive after `12:00`, a warning is added but the
place stays scheduled. iOS has no visibility into any specific place's
opening hours at configuration time (that data lives in `PlaceInput`,
core-api-only) — the config screen's helper text says exactly this,
plainly, rather than iOS attempting any prediction: *"Optimizer günlük
planı bu saat aralığına sığdırır. Mekanların kendi açılış saatleri ayrıca
dikkate alınır."* ("The optimizer fits the daily plan into this time
range. Places' own opening hours are considered separately.")

### Saved itinerary / Apply behavior (Req 8, Req 9)

Untouched, by construction: `TripOptimizerConfigView` (and therefore
these new controls) is never part of the `.viewSaved` path —
`ItineraryHistoryView`'s `NavigationLink` still goes straight to
`TripOptimizerView(mode: .viewSaved(itineraryID:))`, exactly as it has
since v2, never through the config screen. `TripOptimizerViewModel.loadItinerary`
and `.applyToTrip` were not modified in any way by this milestone — no
new parameter, no new call site, no behavior change. Opening a saved
itinerary still only ever calls `GET /itineraries/{id}`; applying one
still only ever calls `POST /itineraries/{id}/apply`. The preferred-time
controls exist exclusively on the `.generate` path's input side.

## Trip Planning Date

A third, optional control, "Planlama Tarihi," sits above "Planlama
Saatleri" in the same `TripOptimizerConfigView` — lets the user anchor a
generated itinerary to a real calendar date, so day sections read "12
Ağustos 2026" instead of a bare "1. Gün." See `docs/trip-optimizer.md`
"Trip Planning Date" for the backend side of this milestone.

### A. What canonical date concept already existed

**None, on `Trip`/`TripStop`.** Neither has ever had a date/travel-date
field — `Trip.created_at` is an upload timestamp, not a trip date, and
`TripStop` has no time-related column at all. The *only* prior artifact
was `OptimizeTripRequest.start_date` (`Optional[str] = None`) — already
fully wired through the request layer and into
`OptimizationConstraints.start_date` → `OptimizedDay.date` (both
strategies compute this via a shared `_date_for` helper) — but that
computed value was silently discarded before ever reaching an API
response; `TripItinerary.params` stored the original request (including
`start_date`, if given) purely as a write-only audit blob, never read
back. iOS never sent `start_date` before this milestone (see "Optimizer
Configuration → Request construction," which explicitly listed it among
the fields deliberately still omitted).

### B. Whether backend/API changes were necessary

**Yes, but minimal — no migration, no new request field.** Two small
core-api changes (see `docs/trip-optimizer.md` "Trip Planning Date → What
changed" for the full detail): `ItineraryDayResponse` gained
`date: Optional[str] = None`, and `SqlOptimizationRepository.get_itinerary`
now reads the itinerary's own persisted `start_date` back out of `params`
and computes each day's `date` via the *existing* `_date_for` helper
(imported, not reimplemented). **mobile-bff and web-bff needed zero
changes** — both already mirror `start_date` on the request side, and
both are pure `resp.json()` passthroughs on the response side, so the new
`date` field flows through automatically.

### C. Exact date representation chosen and why

Wire format: `"YYYY-MM-DD"`, matching core-api's `start_date`/`OptimizedDay.date`
exactly (`datetime.date.isoformat()`). Internally, a new value type,
`PlanningDate` (`Core/Models/PlanningDate.swift`), carries the config
screen's chosen date — same design language as `ClockTime`
(`Preferred Start/End Time Controls`): a bare `(year, month, day)` triple,
**not** `Date` (a calendar date has no time-of-day, no timezone — `Date`
would carry irrelevant complexity for no benefit), with `apiValue`
producing the `"YYYY-MM-DD"` string only at the network boundary
(`Endpoint.body`'s `.optimizeTrip` case) and a `Date` bridge
(`asDate`/`init(date:)`) that exists *only* to satisfy
`DatePicker(displayedComponents: .date)`, which has no native
timezone-less calendar-date type to bind to.

On the *display* side (an already-generated or saved itinerary's day
list), no new type was needed: `ItineraryDay.date: String?` is a plain
Codable field (mirrors `ItineraryStop.arrivalTime: String?`'s own "raw
string, formatted on demand" convention), and a new `ItineraryDay.formattedDate: String?`
computed property converts it to `"12 Ağustos 2026"` — the exact same
`Itinerary.formattedCreatedAt` pattern already established, just with a
new parser. `APIDate` (the project's existing, single date-utility home
— already used for `created_at`) gained `parseDateOnly(_:)`, because its
existing `parse(_:)` only handles core-api's full `T`-separated datetime
strings, not a bare calendar date — a genuinely different wire format,
not a variant of the existing one.

### D. Multi-day semantics

Day 1 = the chosen date, Day 2 = Day 1 + 1 calendar day, Day 3 = Day 1 + 2
calendar days, etc. — **entirely backend-derived**, via `_date_for`
(`date.fromisoformat(start_date) + timedelta(days=day_index)`), pure
calendar-date arithmetic with no time-of-day component to accumulate
error or drift across a DST-adjacent boundary (moot anyway — see
"Timezone" below). **iOS performs no date arithmetic of its own** —
per Req 6 "the backend remains the source of truth" (the same principle
`OptimizerRouteCalculator` already established for routing, and
`isTimeRangeValid` established for time validation): the client only
ever *displays* `ItineraryDay.date` values the backend already computed,
whether the itinerary was just generated or reloaded from history. This
is deliberate — duplicating `_date_for`'s arithmetic in Swift would risk
the two implementations silently disagreeing at a month/year boundary;
not duplicating it means there is only one place this logic can ever be
wrong.

### E. Timezone behavior

**None — matching the rest of the system exactly.** Every date/time value
already flowing through this feature (`preferred_start_time`,
`arrival_time`, `departure_time`, and now `start_date`/`date`) is a bare,
timezone-less string; there is no timezone concept anywhere in the
backend domain (`Trip`, `TripStop`, `TripItinerary`, either strategy) or
in the iOS models built on top of them. `PlanningDate` follows the
identical convention: `Calendar.current` is used only to read/write
`(year, month, day)` components off a bridging `Date` for `DatePicker`
purposes — never to reason about "what time is it right now," never
compared against a `TimeZone`, never serialized with an offset. This
milestone does not introduce timezone support (explicitly out of scope,
Req 15) precisely because nothing in the architecture it extends has any
notion of timezone to begin with — inventing one here would be a novel
addition, not filling a gap the domain already implied.

### Architecture/design decision: extend, don't duplicate (Req 11)

`preferredStartDate: PlanningDate?` lives directly on the existing
`TripOptimizerConfigViewModel` — no second configuration object. Unlike
`preferredStartTime`/`preferredEndTime` (which always have a concrete
value, backend defaults `"09:00"`/`"18:00"`), `preferredStartDate`
follows `durationDays`'s **optional/"Otomatik"** pattern instead: it
starts `nil` ("no date"), because core-api has no default date to fall
back to — omission isn't a fallback-to-a-default, it's a genuinely
different, and equally valid, request shape (`days[].date` just stays
`null`).

```swift
private(set) var preferredStartDate: PlanningDate? = nil

func setPreferredStartDate(_ date: PlanningDate?) {
    preferredStartDate = date
}
```

One setter, not increment/decrement (there's no natural "step" for a
calendar date the way there is for a day count) — `nil` clears it, any
`PlanningDate` sets it. `canOptimize` is **deliberately unaffected** by
this field — an absent date is always a valid configuration, never a
blocking one (unlike an invalid time range).

### UI (Req 10)

```
Planlama Tarihi
┌─────────────────────────────┐
│ ◯ Tarih belirtilmedi          │   ← Toggle, off by default
└─────────────────────────────┘
Belirtilmezse günler yalnızca sıra numarasıyla gösterilir (1. Gün, 2. Gün, …).
```

Toggled on:

```
Planlama Tarihi
┌─────────────────────────────┐
│ ● Belirli bir tarih           │
├─────────────────────────────┤
│ Tarih              12 Ağustos 2026 │
└─────────────────────────────┘
Günler bu tarihten itibaren gerçek takvim günleri olarak gösterilir.
```

A `Toggle` (not a stepper, not a "clear" button) is the enable/disable
affordance — a calendar date has no natural "off" value the way
duration's decrement-to-`Otomatik` gesture does, so an explicit on/off
switch is the clearest way to represent "optional." Turning it on seeds
`PlanningDate(date: Date())` (today) as a reasonable starting point, not
an arbitrary one — the user can change it immediately. The `DatePicker`
only appears while enabled, uses SwiftUI's native `.date`
`displayedComponents` (no custom picker built — none existed to reuse,
same situation `ClockTime`'s `DatePicker(.hourAndMinute)` was in), and is
wrapped in `.environment(\.locale, Locale(identifier: "tr_TR"))` for a
consistent Turkish month name regardless of device region — the same
locale-forcing precedent `APIDate`/the time-controls card already
established. The whole section reuses the identical
surface/border/corner-radius card recipe `durationSection`/
`preferredTimeSection` already use (Req 10 "keep the UI consistent").

Section ordering in the scroll view: Places → Duration → **Date** → Time
— Date before Time, matching the milestone's own mockup.

### Request wire format

`Endpoint.optimizeTrip` gained one more optional associated value,
default `nil`:

```swift
case optimizeTrip(
    tripID: Int, placeIDs: [Int], durationDays: Int? = nil,
    preferredStartTime: ClockTime = .defaultStart, preferredEndTime: ClockTime = .defaultEnd,
    startDate: PlanningDate? = nil
)
```

`Endpoint.body` adds `start_date` to the JSON payload **only when
non-nil** — the exact same conditional-inclusion pattern `duration_days`
already uses (unlike `preferred_start_time`/`preferred_end_time`, which
are always present — see "Preferred Start/End Time Controls → Request
wire format" for why that pair is different). A request that never
touches the new toggle is therefore **byte-for-byte identical** to a
pre-v9 request — this milestone adds nothing to the wire unless the user
explicitly opts in, satisfying Req 4's backward-compatibility requirement
literally, not just behaviorally.

The full chain, unchanged in shape from how `preferredStartTime`/
`preferredEndTime` already flow: `TripOptimizerConfigView`'s toggle/picker
writes through `TripOptimizerConfigViewModel.setPreferredStartDate` →
"Optimize Et" constructs `TripOptimizerView.Mode.generate(...,
startDate:)` → `TripOptimizerView.load()` forwards it to
`TripOptimizerViewModel.optimize(...)` → `Endpoint.optimizeTrip(...)` →
`.apiValue` converts to `"YYYY-MM-DD"` at the JSON boundary.

### Day-header display

`ItineraryDaySection`'s header, previously always `"\(day.dayIndex + 1). Gün"`,
is now:

```swift
Text(day.formattedDate ?? "\(day.dayIndex + 1). Gün")
```

`formattedDate` is `nil` for every itinerary generated without a planning
date (including every itinerary that existed before this milestone) —
the fallback to the ordinal label is automatic and requires no version
check or migration flag; it falls out of `date` simply being absent from
older/date-less responses.

### Saved itinerary / history behavior (Req 8)

An itinerary loaded from history preserves its planning date **because
the backend does** (see `docs/trip-optimizer.md` "Trip Planning Date →
Why this was safe to add without touching the request contract") —
`TripOptimizerViewModel.loadItinerary` was not modified at all; it already
decodes whatever `Itinerary`/`ItineraryDay` JSON comes back, and `date` is
just one more ordinary field in that JSON. `GET /itineraries/{id}`
re-derives each day's `date` from the itinerary's own persisted
`start_date` on every call — not just the run that created it — so
reopening the same saved itinerary a week later still shows the same
dates. Loading a saved itinerary still never calls `POST
.../optimize` — unchanged, proven by the same
`test_loadItinerary_callsItineraryDetailEndpoint_neverOptimizeEndpoint`
test this feature has had since v2.

### Apply-to-trip behavior (Req 9)

**Unmodified, and nothing needed to change.** `Trip` has no date column —
there is no established product rule that applying an itinerary should
set or overwrite a "trip date," so none was added, and
`SqlOptimizationRepository.apply_itinerary`/`ApplyItineraryResponse` were
not touched. Applying an itinerary still only ever writes
`TripStop`/`Trip.applied_itinerary_id`/`Trip.itinerary_applied_at` — the
exact same fields it always has.

## Date-aware Map Day Selector

v9 taught `ItineraryDaySection` (the day/stop *list*) to show a real
calendar date when one exists. `OptimizerRouteMapSection`'s day-selector
chips — the map's own, separate day-browsing UI — still showed
`"1. Gün"`/`"2. Gün"` regardless, because `OptimizerMapDay` (the map's own
per-day presentation type, distinct from `ItineraryDay`) never carried
`date` at all. This milestone closes that one remaining gap — a pure
display change, nothing else.

### Design decision: extend the existing map data type, don't invent a new one

`OptimizerRouteMapData`/`OptimizerMapDay` already exist specifically to
carry itinerary state into `OptimizerRouteMap` in map-ready form (see "Map
Visualization → why a new component" below) — the correct place for a new
piece of *display* information about a day is on that existing type, not
a new parallel one. `OptimizerMapDay` gained one field:

```swift
struct OptimizerMapDay: Identifiable, Hashable {
    let dayIndex: Int
    let date:     String?              // new — same "YYYY-MM-DD"/nil shape as ItineraryDay.date
    let stops:    [OptimizerMapStop]
    var id: Int { dayIndex }
}
```

`OptimizerRouteMapData.init` copies `ItineraryDay.date` straight across
when building each `OptimizerMapDay` — no transformation, no parsing at
construction time:

```swift
days.append(OptimizerMapDay(dayIndex: day.dayIndex, date: day.date, stops: stops))
```

### A second Swift gotcha, same family as v9's

Adding `let date: String? = nil` directly in `OptimizerMapDay`'s own
property declaration (to keep 18 existing test call sites in
`OptimizerRouteCalculatorTests.swift` compiling without every one of them
naming `date:`) produced a real compile error: `"extra argument 'date' in
call"`. This is **the same underlying Swift rule** that broke
`ItineraryDay`'s `Decodable` synthesis in v9 (see "Trip Planning Date →
Test results" for that incident) — but applied to a *different*
synthesis mechanism this time: a `let` stored property with an inline
default is excluded not just from synthesized `Decodable.init(from:)`,
but from the synthesized **memberwise initializer** too, for any struct,
Codable or not. `OptimizerMapDay` isn't `Decodable`, so v9's specific
symptom (silent `nil` decoding) didn't apply here, but the general rule
did — and this time the compiler caught it immediately (a build error,
not a passing-but-wrong test), rather than requiring a targeted test to
surface it. Fixed identically: a hand-written
`init(dayIndex:date:stops:)` with the default on the *parameter*, not the
*property* — this doesn't touch either synthesis mechanism, since Swift
only special-cases a `let` property that has its default written in the
declaration itself.

### Formatting: reusing `APIDate`, not `PlanningDate`

The chip needs a *shorter* format than `ItineraryDay.formattedDate`'s
`"12 Ağustos 2026"` — the spec's own preferred example (`"12 Ağustos"`,
`"13 Ağustos"`, `"14 Ağustos"`) omits the year entirely, sensible for a
small horizontal capsule. `APIDate` (the project's single existing
date-utility home, already used for `created_at` and `ItineraryDay.date`)
gained one more function, following its own `displayString`'s exact
delegation pattern:

```swift
static func shortDisplayString(from date: Date) -> String {
    date.formatted(.dateTime.day().month(.wide).locale(displayLocale))
}
```

Foundation's `.dateTime.month(.wide)` `FormatStyle` produces the correctly
localized month name for whatever `Locale` it's given (`displayLocale`,
the project's existing forced-`tr_TR` constant) — no hand-maintained
Turkish month-name table exists or was added, satisfying the spec's own
"avoid hardcoding all month names manually if Foundation's localized
DateFormatter/FormatStyle can provide the correct output" directly.

**`PlanningDate` was deliberately *not* used here.** It exists for the
*outgoing* side of this feature (`TripOptimizerConfigViewModel`
constructing a request) — `ItineraryDay.formattedDate` already established
the *incoming*/display side's own pattern in v9 (raw `"YYYY-MM-DD"` string
→ `APIDate.parseDateOnly` → `APIDate.displayString`), entirely independent
of `PlanningDate`. `OptimizerMapDay.chipLabel` follows that exact same
already-established pattern, just with `shortDisplayString` instead of
`displayString` — introducing `PlanningDate` into this path would have
created two different ways to parse the same field within the same
codebase, for no benefit.

### Display logic, co-located on `OptimizerMapDay`

```swift
extension OptimizerMapDay {
    var chipLabel: String {
        parsedShortDate ?? "\(dayIndex + 1). Gün"
    }

    var chipAccessibilityLabel: String {
        if let parsedShortDate {
            return "\(dayIndex + 1). gün, \(parsedShortDate)"
        }
        return "\(dayIndex + 1). gün"
    }

    private var parsedShortDate: String? {
        guard let date, let parsed = APIDate.parseDateOnly(date) else { return nil }
        return APIDate.shortDisplayString(from: parsed)
    }
}
```

`parsedShortDate` is computed once and shared by both public properties —
no duplicated parsing between the visible label and the accessibility
label. Both are pure, `MapKit`/SwiftUI-free computed properties directly
on the same MapKit-free `OptimizerMapData.swift` file "Map Visualization"
already established for exactly this reason (map presentation logic
should be testable without rendering an actual map).

### Fallback behavior (Req 2)

`date == nil` (an itinerary generated or saved before v9, or one
generated without touching the new "Planlama Tarihi" toggle) →
`parsedShortDate` is `nil` → `chipLabel` falls back to the pre-v10
`"\(dayIndex + 1). Gün"` ordinal exactly as before. A malformed/
unparseable `date` string degrades identically — `APIDate.parseDateOnly`
already returns `nil` for anything it can't parse (see "Trip Planning
Date → C. Exact date representation"), so `chipLabel` can't distinguish
"no date was ever set" from "a date was set but couldn't be parsed"; both
produce the same safe ordinal fallback, never a crash, never a raw ISO
string on screen.

### Selection identity: untouched (Req 3)

`OptimizerSelection.swift` was not opened for this milestone. The
day-chip tap handler is unchanged:

```swift
dayChip(title: day.chipLabel, accessibilityLabel: day.chipAccessibilityLabel,
        isSelected: selection.dayIndex == day.dayIndex) {
    selection = OptimizerSelection(dayIndex: day.dayIndex, stopID: nil)
}
```

`day.chipLabel` only changes what text the button *shows*; the closure it
runs on tap still writes `day.dayIndex` into `OptimizerSelection`, exactly
as it always has — `date` never enters `OptimizerSelection` in any form.
`OptimizerMapDay.id` (used by `ForEach`'s own diffing) is likewise still
`dayIndex`, not `date` — two days that happened to carry the same date
string (impossible in practice, since dates are derived from a single
`start_date` + distinct `day_index` values, but not structurally
prevented) would still be distinct, correctly-selectable chips.

### Route behavior: untouched (Req 4)

`OptimizerRouteCalculator.swift` was not opened for this milestone.
`cacheKey(for:)` reads only `day.dayIndex` and `day.stops` — adding a new
stored property to `OptimizerMapDay` has no effect on what that function
computes, since Swift functions only read the specific properties they
reference, not "the whole struct." Concretely: switching the selected day
still triggers `.task(id: selection.dayIndex)` (keyed on the `Int`, not on
any label), the same cache lookup/in-flight/camera-refit logic in
`OptimizerRouteMap`/`OptimizerRouteCalculator` runs unmodified, and
`OptimizerRouteCalculatorTests.swift`'s full 18-test suite (all of it
directly constructing `OptimizerMapDay` values, none of them touched)
passing unchanged is the regression proof.

### Accessibility (Req 7)

`dayChip` gained an `accessibilityLabel` parameter (previously VoiceOver
just read whatever `Text(title)` visually showed) and
`.accessibilityAddTraits(isSelected ? [.isSelected] : [])`. For a date
chip, the accessibility label combines the ordinal *and* the date —
`"1. gün, 12 Ağustos"` — deliberately more information than the visual
`"12 Ağustos"` alone, since a VoiceOver user swiping through chips doesn't
have the same left-to-right positional context a sighted user gets from
the chip's position in the row. The `"Tümü"` chip's own accessibility was
left as its default (the word is already unambiguous on its own) plus the
same new selected-trait handling, applied uniformly to every chip through
one shared `dayChip` helper rather than a special case.

### Generate and saved modes (Req 8)

Both flow through the exact same `OptimizerRouteMapSection(itinerary:)` →
`OptimizerRouteMapData(itinerary:)` → `OptimizerMapDay` chain regardless
of whether `itinerary` came from `TripOptimizerViewModel.optimize` or
`.loadItinerary` — neither of those methods was touched by this
milestone, and this milestone adds no new network call anywhere. A saved
itinerary's chips show its own persisted date exactly as a freshly
generated one's do, because both are the same `Itinerary` value flowing
through the same, unmodified code path.

## Persistent Optimizer Route Cache

A performance-only milestone: `OptimizerRouteCalculator`'s successful
`MKDirections` route results now survive leaving and reopening the same
itinerary, instead of living only as long as a single `TripOptimizerView`
push. No API semantics, request/response shapes, or on-screen behavior
change — a cache hit simply skips the network call and shows the same
route it would have shown anyway, just without the wait.

### Why this was needed

v6 ("Real Road Route Visualization") shipped `OptimizerRouteCalculator`
with an in-memory cache keyed by day+stops, but that cache lived inside
the calculator instance itself, and `OptimizerRouteMapSection` recreated
a fresh calculator (`@State`) every time its own view identity was
recreated — i.e. every fresh navigation push. v6's own docs called this
out explicitly as a known limitation ("Cache is per-screen-instance, not
persisted... reopening the same itinerary later... recomputes every
route from scratch") and it was ranked #1 in "Future UI improvements"
after v9. The most common way to trigger this: open a saved itinerary
from Itinerary History, wait for its routes to draw, back out, reopen the
exact same saved itinerary — every leg was re-requested from
`MKDirections`, even though nothing about that itinerary had changed.

### Architecture: `OptimizerRouteCalculator` → `OptimizerRouteCache` → in-memory app-session storage

A new type, `OptimizerRouteCache` (`Components/OptimizerRouteCache.swift`),
owns the cross-screen storage. `OptimizerRouteCalculator` is not aware of
"the app" or any global state — it simply receives an `OptimizerRouteCache`
as a constructor dependency (`init(provider:cache:)`, `cache` defaulting
to a fresh private instance so every existing test/call site that never
mentions caching keeps working unmodified) and calls two methods on it,
`coordinates(for:)` and `store(_:for:)`. This mirrors Req 14's stated
shape exactly (calculator → cache → storage) and avoids the rejected
alternative (a bare global singleton the calculator reaches into
directly) — swapping in a differently-scoped or differently-bounded cache
later would only touch this one constructor parameter.

**Ownership/DI**: `OptimizerRouteCache` is created once in
`TripClipApp.swift` (`@State private var optimizerRouteCache =
OptimizerRouteCache()`) and injected via `.environment(optimizerRouteCache)`
— the *exact* same pattern already used for `AuthEnvironment`, not a new
DI mechanism. `TripOptimizerView` reads it via
`@Environment(OptimizerRouteCache.self)` and passes it as a plain `init`
parameter to `OptimizerRouteMapSection`, which uses it to seed its
`@State private var calculator`'s initial value
(`OptimizerRouteCalculator(cache: routeCache)`). This last hop is a
constructor parameter rather than `OptimizerRouteMapSection` reading
`@Environment` itself, because SwiftUI does not populate a view's
`@Environment` properties until `body` is about to run — `init` (where a
custom `@State` initial value must be assigned) runs earlier, before
environment injection — so the value has to arrive as an explicit `init`
argument instead. `OptimizerRouteCache` itself is marked `@Observable`
purely as a mechanical requirement of that same `.environment(_:)`
injection API (Swift's Observation framework requires it for type-based
environment lookup) — no SwiftUI view ever reads its properties directly,
so this adds no reactive overhead in practice.

### Cache lifetime

**App-session scoped, in-memory only.** Lives exactly as long as
`AuthEnvironment` does: created once at app launch, discarded when the
app process ends (backgrounded-and-later-killed, force-quit, device
restart). Not persisted to disk, Core Data, or SwiftData, and Req 19
explicitly excluded all of those. This was a deliberate choice, not a
shortcut:

- Every cached entry is trivially, cheaply recomputable — one
  `MKDirections` request per leg. There's no "expensive computation worth
  protecting across app launches" the way there is for, say, the AI video
  pipeline's results.
- A disk-backed cache would need a schema, a migration story, and its own
  invalidation/eviction policy on top of the one already needed here —
  real complexity for a cache whose entire purpose is to avoid *redundant
  requests within a session*, not to work offline or survive a restart.
- The existing `PersistenceController` (Core Data) in this codebase is
  reserved for the video-analysis "saved library," a genuinely expensive,
  user-visible dataset — conflating an ephemeral route-geometry cache with
  that layer would blur what Core Data is *for* in this app.

### Cache identity / key — extended in v12

Two related keys exist, both static functions on
`OptimizerRouteCalculator`, both built from `OptimizerMapDay` fields —
never a bare, unrelated UUID (Req 15's "not a UUID unless that UUID is a
stable identity for the itinerary represented"):

- **`cacheKey(for: OptimizerMapDay, mode:)`** — the *day*-level structural
  identity, used for in-flight de-duplication (unchanged purpose from v6,
  now additionally itinerary- and, as of v12, transport-mode-qualified):
  `"itinerary=<id>|day=<index>|mode=<mode>|<stopID>@<lat>,<lng>|…"`.
- **`legKey(day:from:to:mode:)`** *(private)* — the finer-grained
  *leg*-level identity the persistent cache actually keys on:
  `"itinerary=<id>|day=<index>|mode=<mode>|<fromStopID>@<fromLat>,<fromLng>-><toStopID>@<toLat>,<toLng>"`.

(`mode=<mode>` was added in v12 — see "Optimizer Route Transport Mode →
Cache identity — CRITICAL" below for the full reasoning. Both functions
default `mode` to `.automobile`, so this section's description of the
pre-v12 key shape is still exactly what you get if you never pass a
non-default mode.)

**Why itinerary identity had to be added (Req 4, Req 15).** v6's original
`cacheKey` was `"day=<index>|<stopID>@<lat>,<lng>|…"` — no itinerary
component. That was safe under v6's scoping (one calculator instance per
screen, never shared across itineraries), but this milestone's entire
point is sharing one cache across *different* screen visits — potentially
to *different* itineraries. Two different itineraries can plausibly
produce an identical day+stop shape: `ItineraryStop.id` is `"<dayIndex>-
<orderIndex>-<placeID>"`, not a value unique to one optimizer run, so the
same trip optimized twice (or two different trips sharing a place at the
same day/position) could otherwise collide. `OptimizerMapDay` gained a
new `itineraryID: Int` field (populated from `Itinerary.id`, the real
persisted database identifier, in `OptimizerRouteMapData.init`) to close
this gap — the same "extend the existing map data type" pattern v10 used
for `date`. `OptimizerRouteMapDataTests.test_init_propagatesItineraryID_intoOptimizerMapDay`
and `OptimizerRouteCalculatorTests.test_cacheKey_differsForDifferentItineraryID_evenWithIdenticalDayAndStops`
cover this directly.

**Why leg-level, not day-level (Req 9).** Reusing v6's day-level key for
the persistent cache would mean either caching a whole day only once
*every* leg in it succeeded (losing any day with even one flaky leg), or
caching a day that includes a straight-line fallback as if it were a real
route (baking a transient failure in permanently). Neither satisfies Req
9 ("successful legs may be cached; failed legs must remain retryable; do
not cache an entire day as successful when individual route segments
failed"), so the persistent cache is keyed per-leg instead: each
consecutive stop pair is looked up/stored independently.

~~**Transport mode was deliberately left out of the key.**~~ True as of
v11 (`MKDirectionsRoutingProvider` was hardcoded to `.automobile`, so a
mode component would have been needless complexity with no behavioral
difference) — **no longer true as of v12**, which added exactly the
`mode=<mode>` component this paragraph predicted would eventually be
needed. See "Optimizer Route Transport Mode → Cache correctness —
CRITICAL" below for the full v12 design.

### What is cached

Only `[CLLocationCoordinate2D]` — the polyline point list for one
successfully routed leg. Never `MKRoute`, `MKPolyline`, `MKMapView`, or
any `Observable`/SwiftUI state (Req 11) — `OptimizerRouteCache.swift`
doesn't even `import MapKit`. This is the same minimal representation
`OptimizerRouteSegment` already wrapped for a single screen visit; the
persistent cache just stores the raw coordinates one layer further out so
a fresh `OptimizerRouteCalculator` can reconstruct an `OptimizerRouteSegment(coordinates:isRoaded: true)`
from it without ever touching `MKDirections` again.

### Failure and invalidation behavior (Req 5, Req 8, Req 9)

- **Failed legs are never written to the cache.** In
  `OptimizerRouteCalculator.load`'s per-leg loop, `cache.store(...)` is
  only reached inside the `do` block's success path — the `catch` branch
  (straight-line fallback) never calls it. A later visit to the same
  itinerary/day naturally retries exactly that leg, and only that leg.
- **Partial-failure days cache only their successful legs.** Because
  caching is per-leg, a 3-stop day where leg 1 succeeds and leg 2 fails
  ends that visit with leg 1 cached and leg 2 not — a subsequent visit
  reuses leg 1 from cache (no request) and retries only leg 2.
- **Stale-route protection reuses the existing structural identity rather
  than a TTL.** A changed stop order, added/removed stop, or moved
  coordinate all change which `legKey` strings get looked up (different
  from/to pairs, or the same pair with different embedded coordinates),
  so an outdated route can never be served for a changed input — no
  time-based expiry was needed or added, matching Req 5's explicit
  preference.
- **A cancelled in-flight task never writes to the cache**, even if its
  underlying `MKDirections` call happens to complete after cancellation.
  `Task.isCancelled` is re-checked immediately after each `await
  provider.route(...)` returns, before appending the segment or calling
  `cache.store`, so a stale/no-longer-wanted in-flight result can't leak
  into a shared cache another screen instance might read from moments
  later.

### Memory / boundedness (Req 11)

`OptimizerRouteCache` enforces a simple LRU cap, default capacity 500 legs
— generous for realistic usage (a handful of itineraries, each a handful
of days, each a handful of legs, revisited across a session) without
being unbounded. Reading an entry (a cache hit) also refreshes its
recency, so actively-revisited itineraries are the least likely to be
evicted. The implementation is a plain `Dictionary` plus a small array
tracking access order — intentionally not a doubly-linked-list LRU or any
more elaborate structure, since at a 500-entry ceiling the linear
touch/evict cost is trivial and a fancier structure would be
over-engineering for this milestone's needs (Req 12).

### Concurrency (Req 12)

`OptimizerRouteCache` is a plain `@MainActor final class`, matching every
other stateful type in this feature (`OptimizerRouteCalculator`,
`TripOptimizerViewModel`, `AuthEnvironment`) — not a Swift `actor`. An
actor was considered and rejected: every call site that would touch the
cache is already `@MainActor`-isolated (the calculator itself, and the
`Task { [weak self] in ... }` it spawns inherits that isolation the same
way it already did for mutating `self.routes` before this milestone), so
an actor would only add `await` noise at each access point without
removing any actual race — there is no background/off-main-actor code
touching this cache at all.

### In-flight de-duplication (Req 10)

Unchanged in spirit, and intentionally still screen-scoped: `inFlightKeys`/
`inFlightTasks` remain private, per-`OptimizerRouteCalculator`-instance
dictionaries, exactly as in v6. Sharing an in-flight *task* itself across
separate calculator instances (so two simultaneously-open screens showing
the same itinerary could await one shared network request) was
deliberately not built — Req 10 explicitly allowed this ("if sharing
in-flight work across screen instances adds unnecessary complexity, it is
acceptable for in-flight tasks to remain screen-scoped"), and only
*successful results* needed to persist across visits, not in-flight
requests. `test_persistentCache_inFlightDeduplication_stillPreventsRestart_withInjectedCache`
confirms the existing single-instance dedup behavior is untouched by the
new cache parameter.

### UI behavior (Req 16)

No new loading UI exists for a cache hit. When every leg of a requested
day is already cached, `OptimizerRouteCalculator.load` takes a fully
synchronous path (`fullyCachedSegments`) — no `Task` is spawned, `routes[dayIndex].isLoading`
is set straight to `false`, and the day's real route geometry is visible
on the very next `body` evaluation. The existing "loading" straight-line
+ spinner treatment is unchanged for the normal (partial-or-no cache hit)
path. Day selector, stop selection, map camera behavior, bidirectional
map/list interaction, and the v10 date-aware day chips are all untouched
— this milestone never modifies `OptimizerRouteMap`, `OptimizerSelection`,
or `OptimizerRouteMapSection`'s day-chip code, only how
`OptimizerRouteCalculator` sources segment data.

## Optimizer Route Transport Mode

A user-selectable transport mode for the route map's `MKDirections`
calculation — Araba (driving) or Yürüyüş (walking). Explicitly a
**route-visualization preference**, nothing more: the backend optimizer
still decides the itinerary's stop *ordering* completely independently of
which transport mode the map happens to be drawing with. Changing the
mode redraws the *line* the map draws between already-fixed stops; it
never re-requests `/optimize`, never reorders `ItineraryDay.stops`, and
never touches `TripOptimizerViewModel`.

### Supported modes, and why Transit is excluded — superseded by v18

~~Only `.automobile` and `.walking`. Transit was deliberately left out of
this milestone~~ **Resolved in v18 ("Transit Transport Mode"):**
`OptimizerTransportMode` now has a third case, `.transit`, and — exactly
as predicted by the last bullet below — adding it required no change to
the architecture described in this section; only the enum itself grew a
case. The original v12 reasoning is kept here for history:

- Transit routing needs schedule/transfer/agency data `MKDirections`
  doesn't uniformly provide in every region, and can legitimately return
  "no route" far more often than driving/walking for reasons that have
  nothing to do with this app's own correctness — handling that gracefully
  well (distinct from a generic route-not-found leg) would be its own,
  separable scope. (v18: this is exactly what happened — the existing v6
  partial-failure/straight-line-fallback model handled it with zero new
  code.)
- The milestone's own stated goal was to stay "focused and
  production-safe" with exactly two modes; adding a third mode with
  meaningfully different failure characteristics mid-milestone would have
  worked against that.
- Nothing about the architecture below blocks adding it later —
  `OptimizerTransportMode` is a plain `enum`; a `.transit` case (plus its
  own fallback-UX decision) is a contained, additive follow-up. (v18:
  confirmed correct.)

### Model: `OptimizerTransportMode`

A new, small, MapKit-adjacent-but-not-MapKit-typed enum
(`Components/OptimizerTransportMode.swift`):

```swift
enum OptimizerTransportMode: String, CaseIterable, Hashable, Sendable {
    case automobile
    case walking

    var title: String              // "Araba" / "Yürüyüş"
    var accessibilityLabel: String // "Araba ile rota" / "Yürüyüş rotası"
    var symbolName: String         // "car.fill" / "figure.walk"
    var mapKitType: MKDirectionsTransportType
}
```

`mapKitType` is the type's **only** MapKit exposure — `MKDirectionsTransportType`
never appears in SwiftUI `@State`, in `OptimizerRouteCache`, or in any
model `OptimizerRouteCalculator` exposes to its callers; it's read in
exactly one place, `MKDirectionsRoutingProvider.route(from:to:mode:)`,
which is the same MapKit-boundary discipline `OptimizerRoutingProviding`
already established in v6 for `MKRoute`/`CLLocationCoordinate2D`. `Hashable`
lets it key `ForEach(OptimizerTransportMode.allCases, id: \.self)` in the
selector UI; `Sendable` lets it cross into `OptimizerRouteCalculator`'s
`Task { }` closure without a concurrency warning (it's a plain
`String`-backed enum with no reference-type members, so this is automatic,
not something requiring special handling). `title`/`accessibilityLabel`
are hardcoded Turkish strings, matching this feature's own established
convention (the whole app is Turkish-only — see `APIDate.displayLocale`'s
own doc comment) rather than introducing a localization framework this
codebase doesn't otherwise use.

### UI: a compact selector next to the day selector

`OptimizerRouteMapSection` gains a new `transportModeSelector` computed
view, placed directly below `daySelector` (when present) and above the
map itself:

```swift
private var transportModeSelector: some View {
    HStack(spacing: 8) {
        ForEach(OptimizerTransportMode.allCases, id: \.self) { mode in
            dayChip(
                title: mode.title, accessibilityLabel: mode.accessibilityLabel,
                isSelected: selectedTransportMode == mode, systemImage: mode.symbolName
            ) {
                selectedTransportMode = mode
            }
        }
    }
}
```

It **reuses `dayChip`** rather than inventing a second chip component —
`dayChip` gained one new, defaulted parameter, `systemImage: String? = nil`,
so the two existing `daySelector` call sites (which never pass it) are
unaffected, and the transport chips get an SF Symbol (`car.fill`/
`figure.walk`) alongside their label for free. Unlike `daySelector`, this
isn't wrapped in a `ScrollView` — with exactly two options it never needs
to scroll, and a bare `HStack` is simpler (matches the "do not create a
large settings screen" instruction directly).

`selectedTransportMode` is a new, private `@State var` on
`OptimizerRouteMapSection`, defaulting to `.automobile`. It is
**deliberately not shared** via `OptimizerSelection` the way day/stop
selection is — mode isn't an identity concept the itinerary list needs to
know about, it's a display preference scoped entirely to the map section.
It is also **deliberately not persisted** anywhere (no `UserDefaults`, no
`OptimizerRouteCache` involvement) — every fresh `OptimizerRouteMapSection`
(a new `TripOptimizerView` push) starts back at `.automobile`, matching
the "existing production behavior must remain unchanged" default and
avoiding the persistence layers explicitly ruled out for this milestone.

The selector renders identically in `.generate` and `.viewSaved` modes,
because `OptimizerRouteMapSection` itself has never distinguished between
them (see "Persistent Optimizer Route Cache → Generate and saved modes"
history) — both flow through the same `OptimizerRouteMapSection(itinerary:...)`
construction in `TripOptimizerView`, and this milestone didn't touch that.

### Calculator integration

`OptimizerRouteCalculator.load` gained one new parameter:

```swift
func load(day: OptimizerMapDay, mode: OptimizerTransportMode = .automobile)
```

The calculator still owns everything it owned before this milestone —
loading state, cache lookup, in-flight protection, per-day calculation,
partial-failure handling, straight-line fallback — `mode` is purely an
additional *input* threaded through the same pipeline, not a second
pipeline. `OptimizerRouteMap` was not touched at all: it still only
consumes the plain `[Int: OptimizerDayRoute]` snapshot `load` produces,
with no idea a transport mode exists.

### Lifecycle: two independent `.task(id:)` triggers

`OptimizerRouteMapSection` already had one trigger,
`.task(id: selection.dayIndex) { loadVisibleDayRoutes() }` (v6), for "the
visible day changed, recalculate." This milestone adds a second, sibling
modifier:

```swift
.task(id: selection.dayIndex)      { loadVisibleDayRoutes() }
.task(id: selectedTransportMode)   { loadVisibleDayRoutes() }
```

Two separate `.task(id:)` modifiers, not one combined key, because
SwiftUI's `task(id:)` requires a single `Equatable` value and a tuple
cannot conform to that protocol (tuples aren't nominal types). Each
modifier independently manages its own child task and fires whenever
*its own* id changes; both call the same `loadVisibleDayRoutes()`, which
is safe to call redundantly (`calculator.load` is already idempotent
against a same-key in-flight/cached request, a guarantee that predates
this milestone) — so both firing together on first appearance costs
nothing beyond a no-op second call.

`loadVisibleDayRoutes()` itself now reads `selectedTransportMode`:

```swift
private func loadVisibleDayRoutes() {
    for day in mapData.visibleDays(selectedDayIndex: selection.dayIndex) {
        calculator.load(day: day, mode: selectedTransportMode)
    }
}
```

**Selecting a stop in the same day does not restart routing.** Stop
selection changes `selection.stopID`, not `selection.dayIndex` or
`selectedTransportMode` — neither `.task(id:)` observes `stopID`, so
neither refires. This is the exact same guarantee v6 already established
for day-level selection, now additionally verified to hold for mode
(`test_repeatedLoad_sameMode_doesNotRestartRouting`).

**Switching mode clears the current day's displayed route, then
recalculates for the new mode.** `OptimizerRouteCalculator.load`'s
existing "day-scoped `inFlightKeys`/`inFlightTasks`, keyed by the day's
current structural identity" logic (unchanged in shape since v6) does
this automatically once `mode` participates in that identity: a mode
switch produces a different `cacheKey`, so the day's previous
in-flight/completed state no longer "matches," any stale in-flight task
for that day is cancelled, and `routes[day.dayIndex]` is immediately
overwritten with a fresh straight-line-fallback + `isLoading: true` state
— the *old* mode's routed polyline never lingers on screen while the new
mode's request is outstanding
(`test_switchingMode_immediatelyClearsPreviousModesRoute_showsLoadingForNewMode`
observes this transition directly via an `AsyncGate`-held second request).
If the new mode was already cached for that day (the user had visited it
before), this same mechanism instead hits the synchronous
`fullyCachedSegments` fast path — no visible loading flash at all.

**Switching to a different day continues to respect that day's own
cache/in-flight state, regardless of mode.** Day isolation was already a
day-index-keyed guarantee (`routes`/`inFlightKeys`/`inFlightTasks` are all
`[Int: ...]`); mode doesn't change that shape, it only changes what
*content* ends up under a given day's key
(`test_daySwitching_remainsIsolated_regardlessOfTransportMode`).

### Cache correctness — CRITICAL (Req 4)

The single most important correctness property this milestone had to
preserve: **two otherwise-identical legs must never share a cached result
across transport modes.** Both `cacheKey(for:mode:)` and the private
`legKey(day:from:to:mode:)` gained a `mode=<rawValue>` component (see
"Persistent Optimizer Route Cache → Cache identity / key — extended in
v12" above for the exact format). Concretely:

```text
itinerary=42|day=0|mode=automobile|A@lat,lng->B@lat,lng
itinerary=42|day=0|mode=walking|A@lat,lng->B@lat,lng
```

are two distinct `OptimizerRouteCache` entries, never one overwriting the
other. This was verified end-to-end by
`test_transportModeCache_drivingThenWalkingThenBackToDriving_eachModeIndependentlyCached`
— a single flowing test that drives, repeats driving (cache hit, no new
request), switches to walking (new request), repeats walking (cache hit),
then switches *back* to driving and confirms the **original** driving
result is served from cache with **zero** new requests, proving the
driving entry was never evicted or overwritten by the walking one. A
second test, `test_transportModeCache_bothModesCoexist_inSameSharedCache`,
proves the same thing from a "reopen the screen" angle: a brand-new
`OptimizerRouteCalculator` sharing only the `OptimizerRouteCache` (not the
first calculator's in-memory `routes`/in-flight state) can independently
resolve *both* modes for the same day with no provider calls at all,
confirming both entries genuinely live in the shared cache, not in
either calculator's own transient state.

The existing structural-invalidation guarantees (a changed stop order or
moved coordinate invalidates the affected leg's cache entry — see
"Persistent Optimizer Route Cache → Failure and invalidation behavior")
continue to hold per-mode, unchanged in mechanism:
`test_transportModeCache_structuralInvalidation_stopOrderChange_stillInvalidatesCache`
re-runs v11's own stop-reorder test with an explicit `.walking` mode to
confirm the two concerns (structural identity, transport-mode identity)
compose correctly rather than one accidentally masking the other.

**The cache was never cleared wholesale on a mode switch** — that was
explicitly ruled out (Req: "do not solve this by clearing the entire
cache when the mode changes... the cache must remain useful for both
modes"), and the per-leg-key design above makes a blanket clear
unnecessary: each mode's entries simply live alongside the other's under
different keys, and normal LRU eviction (unchanged from v11, see
"Persistent Optimizer Route Cache → Memory / boundedness") is the only
eviction mechanism, exactly as it was before this milestone.

### `MKDirections` / `MKDirectionsRoutingProvider`

```swift
struct MKDirectionsRoutingProvider: OptimizerRoutingProviding {
    func route(
        from: CLLocationCoordinate2D, to: CLLocationCoordinate2D, mode: OptimizerTransportMode
    ) async throws -> [CLLocationCoordinate2D] {
        let request = MKDirections.Request()
        request.source        = MKMapItem(placemark: MKPlacemark(coordinate: from))
        request.destination   = MKMapItem(placemark: MKPlacemark(coordinate: to))
        request.transportType = mode.mapKitType
        ...
    }
}
```

`OptimizerRoutingProviding.route(from:to:)` gained a required `mode:`
parameter — this is the one place this milestone accepted a genuine
protocol-signature break rather than a defaulted addition, since the
protocol itself has exactly two conformers, both owned in this codebase
(`MKDirectionsRoutingProvider` and the test double below), and the
milestone's own spec explicitly asked for this seam to be updated. Every
*caller* of `route(...)` (there is exactly one, inside
`OptimizerRouteCalculator.load`) was updated alongside it in the same
change.

`FakeOptimizerRoutingProvider` (the `OptimizerRoutingProviding` test
double, unchanged in every other respect since v6) now records the
requested mode on each `Call`:

```swift
struct Call {
    let from: CLLocationCoordinate2D
    let to:   CLLocationCoordinate2D
    let mode: OptimizerTransportMode
}
```

so a test can assert `fake.calls[0].mode == .walking` directly —
`test_load_omittingMode_reachesProviderAsAutomobile` and
`test_load_walkingMode_reachesProviderAsWalking` are the two tests that
exist specifically to prove the mode a caller selects is the mode that
actually reaches the routing layer, not just that *some* request was
made. `resultProvider`'s own two-argument closure signature
(`(from, to) -> Result<...>`) was deliberately left unchanged — every
pre-existing test that sets it (partial-failure, cancellation, etc.)
still compiles untouched; tests that specifically care about mode read it
off `calls`, not off `resultProvider`.

### Backward compatibility (Req 12)

`OptimizerRouteCalculator.init(provider:cache:)` was **not** touched —
mode is a per-`load()`-call input (it can legitimately change many times
across one calculator's lifetime as the user toggles the selector), not a
calculator-wide constant fixed at construction, so it doesn't belong on
`init` at all. Every other signature that gained `mode` did so via a
defaulted parameter set to `.automobile`:

- `OptimizerRouteCalculator.load(day:mode: = .automobile)`
- `OptimizerRouteCalculator.cacheKey(for:mode: = .automobile)`

so every pre-v12 call site — every test in `OptimizerRouteCalculatorTests.swift`
written before this milestone, and the production call sites that existed
before `OptimizerRouteMapSection` grew its selector — compiles completely
unchanged and produces byte-for-byte the same cache keys and the same
`.automobile` `MKDirections` requests as before. `test_cacheKey_omittingMode_defaultsToAutomobile`
and `test_load_omittingMode_reachesProviderAsAutomobile` assert this
directly, not just by absence of a compile error.

### Fallback / partial-failure / cancellation behavior (Req 8)

Unchanged in semantics, verified unchanged in practice:

- A failed leg still falls back to a straight two-point line and is still
  **never** written to the cache, for whichever mode was being requested
  (`test_transportModeCache_failedRequest_isNeverCached_regardlessOfMode`).
- A partial-failure day (some legs succeed, one fails) still resolves the
  successful legs and degrades only the failed one, now confirmed for
  `.walking` specifically (`test_partialFailure_stillWorksForWalkingMode`)
  — the per-leg loop and its `do`/`catch` were not restructured, `mode`
  just flows through as one more parameter to `provider.route(...)`.
- `cancelAll()` and the "cancellation must not write to the cache" ordering
  (checking `Task.isCancelled` immediately after `await provider.route(...)`
  returns, before appending the segment or calling `cache.store`) are
  unchanged code paths, re-verified with a non-default mode
  (`test_cancelAll_stillWorksWithNonDefaultTransportMode`).

### Map rendering (Req 9)

Not touched: `OptimizerRouteMap`'s day-colored pins, per-day polyline
drawing, `isRoaded`-driven dashed/solid line style, camera fitting, and
the v7 bidirectional map/list interaction are all exactly as they were —
this milestone's only visible effect on the map itself is that the
polyline geometry the calculator hands to `OptimizerRouteMap` traces a
driving or walking route depending on the selector, using the *same*
rendering code either way. Per the requirement, there is deliberately no
separate color or line style distinguishing "driving route" from "walking
route" on the map — `isRoaded` (real route vs. straight-line fallback)
remains the only visual distinction that exists.

### Accessibility (Req 10)

Follows the exact pattern v10 established for the date-aware day chips:
`dayChip`'s existing `.accessibilityLabel(accessibilityLabel)` +
`.accessibilityAddTraits(isSelected ? [.isSelected] : [])` apply
unchanged to the transport chips, since `transportModeSelector` calls the
same `dayChip` helper. A VoiceOver user hears `"Araba ile rota"` or
`"Yürüyüş rotası"` (not just the bare visual `"Araba"`/`"Yürüyüş"`), plus
the system's own "selected" trait announcement for whichever mode is
currently active — no new accessibility mechanism was introduced, the
existing one was simply reused for a second chip group.

### UI/state testing (Req: "test the minimum amount necessary... do not
introduce snapshot tests or unnecessary UI infrastructure")

`selectedTransportMode` itself is private `@State` inside a SwiftUI
`View` struct and is not unit-tested directly, for the same reason
`OptimizerRouteMapSection`'s other `@State` (`calculator`) never has
been: this project's own established convention (see
`OptimizerSelectionTests.swift`'s doc comment: "the actual SwiftUI/MapKit
wiring around it... is UI glue verified by the build + manual/simulator
smoke check, not unit tests") is to unit-test the *pure logic* a View
delegates to, not the View's own trivial state mutations. That pure logic
is exactly what `OptimizerTransportModeTests.swift` (the model) and the
new `OptimizerRouteCalculatorTests.swift` cases (the integration — mode
reaching the provider, mode participating in cache identity, lifecycle
behavior) cover. No snapshot tests or XCUITest automation were added,
consistent with every prior milestone's testing approach in this
environment.

## Persistent Optimizer Map Selection

The day and stop the user had selected on the route map — `OptimizerSelection`
— now survives leaving `TripOptimizerView` and reopening the same
itinerary, for the remainder of the current app session. Before this
milestone, `selection` was plain `@State`, always starting at
`OptimizerSelection()` ("Tümü", no stop) on every fresh screen push, even
for the exact same itinerary visited moments earlier.

### Scope: session-scoped, in-memory only (Req 1)

No disk, no `UserDefaults`, no Keychain, no Core Data/SwiftData, no
backend persistence, no `NotificationCenter`. A selection is two optional
values (`dayIndex: Int?`, `stopID: String?`) — cheap enough that
in-memory-only storage, gone the moment the app process ends, is not a
shortcut but the appropriate scope for what this data actually is.

### New type: `OptimizerSelectionStore`

A new type (`Components/OptimizerSelectionStore.swift`), architected
identically to `OptimizerRouteCache` (see "Persistent Optimizer Route
Cache → Architecture" above) — `@MainActor @Observable final class`,
created once in `TripClipApp.swift` (`@State private var
optimizerSelectionStore = OptimizerSelectionStore()`), injected via
`.environment(optimizerSelectionStore)`. No `static let shared` — Req 11
explicitly ruled out a singleton, so there is exactly one app-session-owned
instance, reached the same way `AuthEnvironment`/`OptimizerRouteCache`
already are.

```swift
@MainActor
@Observable
final class OptimizerSelectionStore {
    func rawSelection(for itineraryID: Int) -> OptimizerSelection?
    func store(_ selection: OptimizerSelection, for itineraryID: Int)
    func resolveSelection(for itinerary: Itinerary) -> OptimizerSelection
}
```

`rawSelection`/`store` are a dumb, unvalidated key-value pair (private
`[Int: OptimizerSelection]` dictionary, keyed by `Itinerary.id`) —
`store` never validates anything, because the value it's given always
comes from a live, already-consistent screen selection; staleness can
only arise *between* visits, which is exactly what `resolveSelection`
guards against on the way back out. No LRU/capacity bound was added here
(unlike `OptimizerRouteCache`'s 500-leg cap) — a stored selection is a
few bytes, and a session realistically touches at most a few dozen
itineraries, so an unbounded dictionary was judged proportionate rather
than under-engineered.

### Itinerary isolation — CRITICAL (Req 3)

Every entry is keyed by `Itinerary.id`, never globally by `dayIndex`
alone. Itinerary 42's selection and itinerary 91's selection live under
separate dictionary keys and can never collide, regardless of whether
they happen to share the same day/stop shape —
`test_differentItineraries_haveIndependentSelections` and
`test_switchingBetweenItineraries_thenReturning_restoresOriginalSelection`
(open A, select, open B, select, reopen A, confirm A's selection is
still exactly what it was) verify this directly.

### Validation on restore — CRITICAL (Req 5)

`resolveSelection(for:)` never blindly returns what was stored — every
restore is validated against the itinerary passed in, following this
order (each step only runs if the previous one didn't already resolve):

1. **No stored selection at all** → the pre-existing default,
   `OptimizerSelection()` ("Tümü", no stop) — byte-for-byte the same
   behavior as every milestone before this one.
2. **A `stopID` was stored** → search *every* day of the current
   itinerary for a stop with that id (not just the day that was stored
   alongside it). If found, restore `.focusing(dayIndex: <the day it was
   actually found under>, stopID:)` — the day comes from wherever the
   stop *currently* lives, not from the possibly-stale stored `dayIndex`.
   This single search covers both "nothing changed" (the overwhelmingly
   common case — the stop is found under its original day) and "the stop
   moved to another day" (Req 6's "follow the stop, not the old day")
   with the exact same code path, since the day used for the restored
   selection always comes from where the stop is found *now*.
3. **The stop wasn't found** (deleted, or none was stored) → fall back to
   validating the stored `dayIndex` alone: if that day still exists in
   the itinerary, keep it (no stop) — Req 6 "keep the stored day if that
   day is still valid."
4. **The stored day doesn't exist either** → fall back to the itinerary's
   first available day, no stop (`itinerary.days.first?.dayIndex`).
5. **The itinerary has no days at all** → step 4 already produces `nil`
   for an empty `days` array, so this "empty itinerary → `OptimizerSelection(dayIndex:
   nil, stopID: nil)`" case falls out of the general logic automatically —
   no separate special-case branch was needed.
6. **The stored selection was already "Tümü"** (`dayIndex: nil`) → stays
   "Tümü."

`OptimizerSelectionStoreTests.swift`'s "Validation" group covers every
one of these branches directly, including the deliberately adversarial
"stored `dayIndex` disagrees with where the stop is actually found"
scenario for step 2.

O(total stops + days) at worst (one linear scan) — no network request, no
database query, no route calculation is ever triggered purely to validate
a restore (Req 16).

### Lifecycle: resolved once, right after the itinerary loads (Req 7)

`TripOptimizerView.load()` — the existing function that already calls
`vm.optimize(...)`/`vm.loadItinerary(...)` — gained two lines at the end:

```swift
private func load() async {
    switch mode { /* unchanged */ }
    if let itinerary = vm.itinerary {
        selection = selectionStore.resolveSelection(for: itinerary)
    }
}
```

This runs in the *same* async function, with no `await` between
`vm.itinerary` being populated and `selection` being assigned — so
SwiftUI's next render reflects both together. This matters: `resultContent(itinerary)`
(and the `OptimizerRouteMapSection` inside it) is never actually
constructed with the stale `OptimizerSelection()` default in between —
there is no "Tümü" flash, and no wasted "load every day's route, then
immediately reload just the restored day" request pair. A separate
`.task(id: itinerary.id)` triggered from inside `resultContent` was
considered and rejected specifically because it would introduce exactly
that one-frame-later reassignment (and the wasted all-days route request
it would cause) — putting the two lines directly in `load()`, sequentially
after the existing itinerary fetch, avoids the race entirely without
adding a second async trigger.

No second route-loading mechanism was introduced: once `selection` is
set, the *existing* `OptimizerRouteMapSection.task(id: selection.dayIndex)`
(unchanged since v6, extended for transport mode in v12) reacts exactly
as it always has — it has no idea whether `selection.dayIndex` changed
because the user tapped a day chip or because a restore just happened.

### User interaction updates the store, from one place (Req 8)

`selection` is still mutated in the same three places it always was —
`OptimizerRouteMapSection`'s day chips, its map stop tap handler, and
`ItineraryDaySection`'s row tap forwarded through `TripOptimizerView` —
and **none of those three call sites were touched**. Instead,
`TripOptimizerView` gained a single, centralized sync point:

```swift
.onChange(of: selection) { _, newSelection in
    if let itinerary = vm.itinerary {
        selectionStore.store(newSelection, for: itinerary.id)
    }
}
```

Every `selection` mutation, regardless of origin (including the
`resolveSelection` assignment inside `load()` itself, which just writes
the same value straight back — harmless, and means a never-before-stored
default gets recorded on first visit too), flows through this one
`onChange`. This is what keeps `OptimizerRouteMapSection`/`ItineraryDaySection`
genuinely ignorant of the store's existence (Req 2's "do not put
persistence logic inside those views") — they only ever read/write the
same `OptimizerSelection` they always did. `.onChange`'s own `initial: false`
default (unspecified here) means it never fires for the very first,
un-changed value, so no spurious write happens before the user (or a
restore) actually changes anything.

### No second selection model (Req 4, Req 8)

The store persists exactly `OptimizerSelection` — `dayIndex`/`stopID`, the
same two fields, the same semantics (`nil` dayIndex = "Tümü") that have
existed since v7. No parallel "stored day"/"stored stop" representation
was introduced; `OptimizerSelectionStore` is a dictionary *of*
`OptimizerSelection` values, not a redefinition of what a selection is.

### Interaction with the route cache and transport mode (Req 15)

`OptimizerRouteCache` (v11) was not modified. A restored selection simply
becomes the new `selection.dayIndex`, which flows into the *existing*
`OptimizerRouteCalculator.load(day:mode:)` call exactly as any other day
selection would — if that day's route (for whatever transport mode is
currently selected) was already cached from an earlier visit, it's served
synchronously with no request, precisely v11's own "does the second visit
skip the network request" guarantee, now also true for a *restored*
selection rather than only a freshly-tapped one. No "selection restore"
routing special case exists anywhere in `OptimizerRouteCalculator`.

### `.generate` and `.viewSaved` (Req 12)

Both flow through the identical `load()` → `resolveSelection` →
`onChange` → `store` cycle, because both already flowed through the same
`load()`/`resultContent`/`OptimizerRouteMapSection` chain before this
milestone (see "Persistent Optimizer Route Cache → Generate and saved
modes" for the historical precedent) — this milestone didn't add a
mode-specific branch anywhere.

### Testing (Req 14)

`OptimizerSelectionStoreTests.swift` (16 tests) exercises the store in
complete isolation from `TripOptimizerView`: basic storage (store/retrieve/
update/nil-selection), itinerary isolation (including the A→B→A round
trip), every validation branch from the list above, and a dedicated
"session behavior" test
(`test_sameStoreInstance_secondVisitsSelection...`) that stores a
selection, then calls `resolveSelection` again on the *same store
instance* to stand in for "a second, independent `TripOptimizerView`
instance" — the store itself has no notion of "which screen" is asking,
which is the point: its data outlives any single screen by construction.
The "same-day selection doesn't reload routes" / "restored selection
doesn't cause duplicate requests" concerns from the milestone's own test
list are not re-tested here, because no new routing code path was
introduced for them to regress — they remain covered by the existing,
unmodified `OptimizerRouteCalculatorTests.swift`/`OptimizerSelectionTests.swift`
suites, which this milestone's full-suite run confirms still pass
unchanged.

## Overnight Time Ranges

Primarily a **core-api** milestone — see `docs/trip-optimizer.md`
"Overnight Time Ranges" for the full backend design (`PlanningTimeWindow`,
the continuous-timeline representation, `GreedyDistanceStrategy`/
`ORToolsRouteOptimizationStrategy` both gaining correct midnight-crossing
scheduling). The iOS surface area is deliberately tiny: one changed
property, no UI redesign, no new fields, no date/timezone arithmetic.

### What changed on iOS

```swift
// Before (v8):
var isTimeRangeValid: Bool { preferredStartTime < preferredEndTime }
// After (v14):
var isTimeRangeValid: Bool { preferredStartTime != preferredEndTime }
```

That's the entire production change. `18:00` → `01:00` and `23:30` →
`03:00` — previously blocked, disabling "Optimize Et" — are now accepted;
`09:00` → `18:00` continues to work exactly as before; `09:00` → `09:00`
(equal) remains the one rejected case, matching core-api's own updated
contract (see "Preferred Start/End Time Controls → Validation — superseded
by v14" above for the historical rule this replaced).

### Why iOS needed no more than this

The existing config screen (`TripOptimizerConfigView`, `Planlama Saatleri`
→ Start/End) already used two independent `DatePicker(...,
displayedComponents: .hourAndMinute)` bound to `ClockTime` — a
timezone-less, date-less hour/minute pair (see `ClockTime.swift`'s own doc
comment: "a 'gün içi saat' bir tarihe/saat dilimine sahip değildir"). A
`DatePicker` configured for `.hourAndMinute` has no concept of "which of
two times is chronologically first" baked into its own UI — a user was
always free to *pick* `18:00` for start and `01:00` for end; the only
thing that changed is whether `isTimeRangeValid` then *accepts* that pair.
No new picker, no overnight-specific affordance, no visual indication that
a range "wraps" was added — Req 13's explicit "do not redesign the UI"
constraint made this a validation-only change by design, not by omission.

### What iOS deliberately does not compute

Per Req 14 ("the iOS layer only needs to determine whether the pair is a
syntactically valid planning range... do not duplicate backend scheduling
logic in Swift"), `isTimeRangeValid` does not, and should not, know
*whether* a given range is overnight, what a place's opening hours mean
under it, or how many itinerary days it produces — all of that is
resolved entirely server-side (see `docs/trip-optimizer.md`'s
`_day_relative_window`/`_resolve_arrival`/`PlanningTimeWindow`). iOS's own
`ClockTime` gained no new API (`is_overnight`, `duration`, or similar) —
introducing one would have been exactly the "second, parallel time system"
Req 5 warned against building, mirrored client-side for no behavioral
gain, since the server-side result is what ultimately renders anyway.

### Request wire format: unchanged

`Endpoint.optimizeTrip`'s `preferredStartTime`/`preferredEndTime`
parameters and their `.apiValue` → `"HH:MM"` conversion are byte-for-byte
unchanged — an overnight pair serializes exactly the same way a same-day
pair always did (`"18:00"`, `"01:00"`, two independent strings, no
wraparound marker, no reordering). `OptimizeTripRequest` gained no field;
`Endpoint.swift` required no changes at all this milestone — confirmed by
`git diff` touching only `TripOptimizerConfigViewModel.swift` in
production code.

### Testing

`TripOptimizerConfigViewModelTests.swift` gained: an overnight range
(`19:00 → 09:00`) now asserts `isTimeRangeValid == true` (replacing the
old test that asserted `false` for the same input — the input's meaning
changed, so the assertion had to); both of the milestone's own minimum
examples (`18:00 → 01:00`, `23:30 → 03:00`) asserted valid; `canOptimize`
confirmed `true` for an overnight range with places selected; and the
one still-genuinely-invalid case (equal start/end) re-asserted `false`
via a corrected version of the pre-existing "invalid range blocks
`canOptimize`" test (its old input, `20:00 → 08:00`, was itself an
overnight range under the new semantics and had to be replaced with an
equal-value input to keep testing what it always meant to test).
`OptimizerEndpointTests.swift` gained a direct proof that an overnight
`ClockTime` pair serializes as two independent, unmodified `"HH:MM"`
strings in the request body — no special encoding. `ClockTimeTests.swift`'s
own `Comparable`-conformance tests are untouched (`Comparable` remains a
useful general capability on `ClockTime`; it's simply no longer what
`isTimeRangeValid` itself uses).

## Persistent Optimizer Configuration

The entire optimizer configuration screen — which places are selected,
duration, preferred start/end time, planning date, and (for the map's own
later use) transport mode — now survives leaving `TripOptimizerConfigView`
and reopening it for the *same trip*, for the remainder of the current app
session. Before this milestone, `TripOptimizerConfigViewModel` was plain
`@State`, always starting from scratch (all places selected, "Otomatik"
duration, `09:00`–`18:00`, no date) on every fresh screen push, even for
the exact same trip visited moments earlier.

### Scope: session-scoped, in-memory only

No disk, no `UserDefaults`, no Keychain, no Core Data/SwiftData, no
backend persistence, no database migration. A configuration is six small
values — worth remembering only for the length of the session, not
forever.

### New type: `OptimizerConfiguration`

A plain, `Equatable` value type (`Components/OptimizerConfiguration.swift`)
holding exactly what's needed to reconstruct the screen's state — never a
`TripOptimizerConfigViewModel` instance, never a SwiftUI state object:

```swift
struct OptimizerConfiguration: Equatable {
    var selectedPlaceIDs:   Set<Int>
    var durationDays:       Int?              // nil = Otomatik
    var preferredStartTime: ClockTime
    var preferredEndTime:   ClockTime
    var startDate:          PlanningDate?
    var transportMode:      OptimizerTransportMode
}
```

`durationDays` is `Int?`, not `Int` — deliberately deviating from the
milestone's own illustrative shape, because `TripOptimizerConfigViewModel.durationDays`
was already optional ("Otomatik" = `nil`, since v4) and this type exists
to mirror that ViewModel's real state exactly, not to invent a new
semantic.

### New type: `OptimizerConfigurationStore`

Architected identically to `OptimizerRouteCache`/`OptimizerSelectionStore`
(see "Persistent Optimizer Route Cache → Architecture" and "Persistent
Optimizer Map Selection" above) — `@MainActor @Observable final class`,
created once in `TripClipApp.swift`, injected via `.environment(_:)`. No
`static let shared` — there is exactly one app-session-owned instance,
reached the same way the other two already are.

```swift
@MainActor
@Observable
final class OptimizerConfigurationStore {
    func configuration(for tripID: Int) -> OptimizerConfiguration?
    func save(_ configuration: OptimizerConfiguration, for tripID: Int)
    func remove(for tripID: Int)
}
```

A private `[Int: OptimizerConfiguration]` dictionary keyed by `Trip.id`.
The store itself does dumb, unvalidated storage — it knows nothing about
SwiftUI, networking, `TripStop`, or the optimizer; all validation happens
on the way *out* (see "Reconciliation" below), in
`TripOptimizerConfigViewModel` itself, not in the store.

### Itinerary — sorry, *trip* — isolation (CRITICAL)

Every entry is keyed by `Trip.id`, never globally. Trip 42's configuration
and Trip 91's configuration live under separate dictionary keys and can
never collide — `test_tripIsolation_configurationForTripA_neverAppearsOnTripB`
and `test_tripIsolation_reopeningTripA_afterVisitingTripB_restoresTripAsConfiguration`
(A→B→A) verify this directly, the same shape of proof
`OptimizerSelectionStoreTests.swift` already established for the map
selection store.

### Restoration: synchronous, in `init`

Unlike `OptimizerSelectionStore` (whose restoration has to wait for an
itinerary to load asynchronously — see "Persistent Optimizer Map
Selection → Lifecycle" above), `TripOptimizerConfigViewModel` was already
documented as making **no network call at all** — `stops` is handed to it
directly by the caller. This means restoration can happen fully
synchronously, inside `init` itself, with no async step and therefore no
"flash of defaults" to guard against:

```swift
init(
    tripID: Int = 0, stops: [TripStop],
    configStore: OptimizerConfigurationStore = OptimizerConfigurationStore()
) {
    self.tripID = tripID
    self.stops = stops
    self.configStore = configStore

    let resolved = Self.reconciled(
        saved: configStore.configuration(for: tripID),
        availablePlaceIDs: Set(stops.map(\.placeId))
    )
    // ... assign resolved.* to every stored property ...
    persistConfiguration()
}
```

`tripID`/`configStore` both default (`0` / a fresh, empty store) —
exactly the `OptimizerRouteCalculator.init(provider:cache:)` pattern from
v11 — so every pre-existing test call site
(`TripOptimizerConfigViewModel(stops: stops)`, dozens of them across
`TripOptimizerConfigViewModelTests.swift`) keeps compiling and behaving
identically, unaware persistence exists at all.

### Reconciliation — never blindly restored (Req 9)

`Self.reconciled(saved:availablePlaceIDs:)` validates every field against
the *current* trip before it becomes the initial state:

- **No saved configuration** (first visit) → today's pre-existing
  defaults, byte-for-byte: all places selected, `durationDays = nil`,
  `09:00`–`18:00`, no date, `.automobile`.
- **Selected places** — the saved set intersected with the trip's
  *current* place IDs. The milestone's own worked example is the exact
  contract: saved `[1,2,3,4]`, current trip `[1,2,4,5]` → restored
  `[1,2,4]` — place `3` (removed from the trip) drops out; place `5`
  (never seen before) is **not** auto-selected, even though "select all"
  is the first-visit default — an explicit, previously-recorded selection
  always wins over the default
  (`test_savedSelection_reconciledAgainstCurrentTrip_removedIDsDropped_newIDsNotAutoSelected`).
- **Duration** — clamped into `durationRange` (`1...30`) if somehow out
  of bounds (defensive; the ViewModel itself never lets it drift out of
  range, so this is a "can't currently happen but stay safe" guard, not a
  reachable path); `nil` ("Otomatik") always passes through unchanged.
- **Preferred time** — restored exactly, *including overnight ranges*,
  unless `start == end` (the one rule `isTimeRangeValid` still
  enforces — see "Overnight Time Ranges" above), in which case it falls
  back to `.defaultStart`/`.defaultEnd`. The old, pre-v14 `end > start`
  restriction is deliberately **not** reintroduced here.
- **Start date** — restored as-is; `PlanningDate` has no validity rules
  of its own to apply (any year/month/day triple is accepted, matching
  its own "no date arithmetic" design since v9), so there's nothing
  further to validate.
- **Transport mode** — restored as-is; both cases are always valid.

### Saving: one centralized method, called from every mutator

Per the milestone's own "prefer one centralized save mechanism rather
than scattering `store.save(...)` through every setter" instruction, all
six fields flow through exactly one private method:

```swift
private func persistConfiguration() {
    configStore.save(
        OptimizerConfiguration(
            selectedPlaceIDs: selectedPlaceIDs, durationDays: durationDays,
            preferredStartTime: preferredStartTime, preferredEndTime: preferredEndTime,
            startDate: preferredStartDate, transportMode: transportMode
        ),
        for: tripID
    )
}
```

Every existing mutator (`toggle`, `selectAll`, `deselectAll`,
`setPreferredStartTime`, `setPreferredEndTime`, `setPreferredStartDate`,
`incrementDuration`, `decrementDuration`) gained exactly one added line —
a call to `persistConfiguration()` — plus a new `setTransportMode`
gained the same. `didSet` observers were deliberately **not** used for
this: since `init` assigns every stored property explicitly during
restoration (not via each property's own inline default), a `didSet` on
each property would fire once *per field* during restoration itself,
saving repeatedly with partially-restored, transiently-inconsistent
snapshots before the final one — an explicit call at the end of `init`
(after all fields are set) and at the end of each mutator avoids that
footgun entirely while still keeping the actual "build + save" *logic*
in exactly one place.

### Relationship to the map's own transport selector

`OptimizerConfiguration.transportMode` exists for a downstream purpose:
`OptimizerRouteMapSection` (v12's Araba/Yürüyüş selector) gained a new,
defaulted init parameter, `initialTransportMode: OptimizerTransportMode = .automobile`,
used to seed its own `@State` instead of always starting at `.automobile`.
`TripOptimizerView` reads `OptimizerConfigurationStore` (via
`@Environment`, the same DI seam as `routeCache`/`selectionStore`) and
passes `configStore.configuration(for: itinerary.tripId)?.transportMode ?? .automobile`
when constructing the map section — for **both** `.generate` and
`.viewSaved` modes, since `Itinerary.tripId` is available either way, no
special-casing needed.

At the time this was originally written, the relationship was
**one-directional**: the config screen's restored mode seeded the map's
*initial* value, but a mode change made directly on the map screen was
not written back. **As of v16 ("Persistent Optimizer Transport Mode
Sync"), this is now bidirectional** — see that section below. The config
screen's own `transportMode`/`setTransportMode` still exist purely so the
field is restorable/saveable/testable at the ViewModel level, even
without a picker on this particular screen.

### Distinction from `OptimizerSelectionStore` and `OptimizerRouteCache`

Three session-scoped stores now exist side by side, deliberately kept
separate rather than merged:

| Store | Represents | Keyed by |
|---|---|---|
| `OptimizerConfigurationStore` | how the *next* optimization should be configured | `Trip.id` |
| `OptimizerSelectionStore` | which day/stop is currently *focused* on an *already-generated* itinerary's map | `Itinerary.id` |
| `OptimizerRouteCache` | computed route *geometry* for a leg, keyed by itinerary+day+mode | leg key string |

None of the three was modified to accommodate another — `OptimizerRouteCache`'s
existing per-leg `mode=` cache-key component (v12) already handles
transport-mode variation at the *route data* level; this milestone's
`transportMode` field is a completely separate concern (the *user's
remembered preference*, not cached route results) and was never merged
into it, per the milestone's own explicit instruction.

### What is not persisted

The generated itinerary, its score, warnings, or apply/history state —
none of that lives here or ever will; those already have `TripOptimizerViewModel`,
`OptimizerRouteCache`, and core-api's own persistence respectively. This
store is configuration-only, full stop.

### First-visit behavior: unchanged

With no saved configuration, `reconciled(saved: nil, ...)` reproduces
exactly what `TripOptimizerConfigViewModel.init(stops:)` already did
before this milestone — confirmed directly by
`test_noSavedConfiguration_usesExistingDefaults`.

### Known limitations

- ~~**Map-side transport mode changes don't write back.**~~ **Resolved in
  v16** — see "Persistent Optimizer Transport Mode Sync" below.
- **No user-facing indicator that a configuration was restored** —
  matching the same precedent set by `OptimizerSelectionStore` (v13): the
  screen simply opens already configured, with no toast/banner calling
  attention to it.
- **Session-scoped only** — force-quitting the app (or the OS reclaiming
  it in the background) loses every stored configuration, by design.

### Testing

`OptimizerConfigurationStoreTests.swift` (new) tests the store in
isolation: save/retrieve, missing-trip returns `nil`, overwrite replaces,
`remove` deletes, and trip isolation (including an A→B→A round trip).
`TripOptimizerConfigViewModelTests.swift` gained restoration/reconciliation
coverage (no-saved-config defaults, exact restoration, the selection
reconciliation worked example, duration clamping, invalid-range fallback,
overnight-range restoration, date/transport-mode restoration),
save-on-change coverage (one test per mutator category proving it updates
the store), and ViewModel-level trip-isolation coverage (two
`TripOptimizerConfigViewModel` instances sharing one store never leak
into each other, and reopening Trip A after visiting Trip B restores A's
own configuration).

## Persistent Optimizer Transport Mode Sync

v15 made `OptimizerConfiguration.transportMode` persistent, but only in
one direction: the config screen's restored mode seeded
`OptimizerRouteMapSection`'s *initial* value, and a mode change made
directly on the route map (Araba ↔ Yürüyüş) was never written back into
`OptimizerConfigurationStore`. This milestone closes exactly that gap —
nothing else.

### Architecture/design decision: a callback out, a merge method in

The map component still does not know `OptimizerConfigurationStore`
exists — that constraint from v15 didn't change. Instead,
`OptimizerRouteMapSection` gained one new, defaulted `init` parameter:

```swift
var onTransportModeChanged: ((OptimizerTransportMode) -> Void)? = nil
```

fired from the exact same place `selectedTransportMode` is already
mutated (the transport selector's button action), right alongside it:

```swift
selectedTransportMode = mode
onTransportModeChanged?(mode)
```

This mirrors the pre-existing `onStopSelectedFromMap` pattern in the same
file exactly — a raw, ownership-free event reported upward, with zero
persistence logic in the map component itself.

`TripOptimizerView` supplies the closure and relays it, in one line, to a
new `OptimizerConfigurationStore` method:

```swift
onTransportModeChanged: { mode in
    configStore.updateTransportMode(
        mode, for: itinerary.tripId,
        fallbackSelectedPlaceIDs: Set(itinerary.days.flatMap(\.stops).compactMap(\.placeId))
    )
}
```

`updateTransportMode(_:for:fallbackSelectedPlaceIDs:)` lives on the store,
not in `TripOptimizerView`, so the "how do I merge a partial change into a
possibly-nonexistent configuration" logic stays in exactly one place —
the same "one centralized method" principle v15 already applied to
`persistConfiguration()`:

```swift
func updateTransportMode(_ mode: OptimizerTransportMode, for tripID: Int, fallbackSelectedPlaceIDs: Set<Int>) {
    if var existing = configurations[tripID] {
        existing.transportMode = mode
        configurations[tripID] = existing
    } else {
        var config = OptimizerConfiguration.defaults(selectedPlaceIDs: fallbackSelectedPlaceIDs)
        config.transportMode = mode
        configurations[tripID] = config
    }
}
```

### Why a fallback selection, not an empty one, on first write

If a configuration already exists for the trip (the config screen was
visited at least once — always true for `.generate`, since
`TripOptimizerConfigView` is the only way to reach it), the merge only
ever touches `transportMode`; `selectedPlaceIDs`/`durationDays`/
`preferredStartTime`/`preferredEndTime`/`startDate` are left exactly as
they were (Req: "mode change must not affect places/duration/time/date").

But `.viewSaved` (Itinerary History → a saved itinerary, opened directly)
can reach `TripOptimizerView` **without ever visiting the config screen**
for that trip — so `configurations[tripID]` can genuinely be `nil` when
the map reports its first mode change. Creating a fresh record with an
*empty* `selectedPlaceIDs` there would be actively wrong: if the user
later opens the config screen for the same trip,
`TripOptimizerConfigViewModel.reconciled(saved:availablePlaceIDs:)`
intersects the saved selection with the trip's current places — an empty
saved selection intersected with anything is still empty, so every place
would silently render as deselected, a confusing regression the user
never asked for.

Instead, the store falls back to the *currently displayed* itinerary's
own place IDs (`itinerary.days.flatMap(\.stops).compactMap(\.placeId)`,
supplied by `TripOptimizerView` — the map component itself never computes
this). A later config-screen visit for that trip then starts from "the
places the user was just looking at" rather than "nothing" — not a
perfect substitute for an actual config-screen visit, but a reasonable
one, and never destructive.

`OptimizerConfiguration.defaults(selectedPlaceIDs:)` is a small new
static factory extracted for this — `TripOptimizerConfigViewModel.reconciled(saved: nil, ...)`
now calls the same factory instead of duplicating the same five default
values that used to be inlined there.

### Restoration remains synchronous and unaffected

`OptimizerRouteMapSection`'s own `initialTransportMode` param and its
`_selectedTransportMode` seeding are untouched — a config-screen-restored
`.walking` still seeds the map's chip as `.walking` on first render, with
no visible flash back to `.automobile`. Nothing about the merge logic
above runs at restore time, only at the moment the user actually taps a
transport chip on the map.

### Trip isolation

`updateTransportMode` keys off `tripID` exactly like every other store
operation — updating trip A's mode never touches trip B's stored
configuration, in either direction (A→B→A round trip, and the reverse).
Covered by
`test_updateTransportMode_forTripA_neverAffectsTripB`/`test_updateTransportMode_tripIsolation_roundTrip`.

### Route cache: untouched

`OptimizerRouteCache`/`OptimizerRouteCalculator` were not modified. The
leg cache key already carries `mode=<rawValue>` since v12, so switching
the map's own display mode already re-requests (or cache-hits) the
correct, mode-scoped route independently of anything persisted here —
this milestone only adds a side-channel *notification* of the mode
change, it does not touch how routes are calculated or cached.

### Scope boundaries (explicitly out of scope for this milestone)

Transit mode, route-rendering style, server-side transport-mode
persistence, cross-app-launch persistence, new map features, date/
timezone work, itinerary mutation, and new optimizer strategies — none of
that changed here.

### Testing

`OptimizerConfigurationStoreTests.swift` gained direct coverage of
`updateTransportMode`: merging into an existing configuration touches
only `transportMode` (places/duration/time/date all asserted unchanged),
creating a new configuration from `nil` uses the supplied fallback place
IDs (not empty), reading back after a write reflects the latest mode,
repeated calls persist only the last value, and trip isolation (both a
direct A-doesn't-affect-B check and an A→B→A round trip).
`TripOptimizerConfigViewModelTests.swift` gained one integration-style
test, `test_mapOnlyTransportModeChange_beforeAnyConfigScreenVisit_doesNotEmptySelectionOnLaterVisit`,
proving the exact scenario the fallback exists for: a map-only mode
change with no prior config-screen visit, followed by opening the config
screen, restores the fallback place IDs rather than an empty selection.

`OptimizerRouteMapSection`/`TripOptimizerView` are SwiftUI `View`s and, per
this project's established convention, are not unit-tested directly (no
XCUITest harness here) — the new `onTransportModeChanged` wiring is
exercised at the layer it actually delegates to
(`OptimizerConfigurationStore.updateTransportMode`), which is where the
behavior that matters (what gets persisted, and how) actually lives.

## Optimizer Configuration Transport Mode Picker

Through v16, `TripOptimizerConfigViewModel.transportMode` was fully
persisted, restored, and synced with the route map — but the config
screen itself had no control to change it; the only way to set a mode was
from the map, after generating or opening an itinerary. This milestone
adds that control, purely as a UI addition on top of the architecture
v15/v16 already built.

### No new state — same ViewModel, same store

`TripOptimizerConfigView` gained one new section,
`transportModeSection`, built the same way as every other section on
this screen: a `Binding` that reads `vm.transportMode` and writes through
`vm.setTransportMode(_:)`.

```swift
private var transportModeBinding: Binding<OptimizerTransportMode> {
    Binding(
        get: { vm.transportMode },
        set: { vm.setTransportMode($0) }
    )
}
```

`setTransportMode` already existed (added in v15, exercised only by
tests and by the map's v16 callback until now) and already ends in
`persistConfiguration()`, the same centralized save point every other
mutator uses — so wiring a picker to it required zero ViewModel changes.
There is exactly one owner of "what is this trip's transport mode right
now": `OptimizerConfigurationStore`, keyed by `Trip.id`. The config
screen and the route map are two different *views* onto that one value,
never two competing sources of truth.

### UI: a native segmented `Picker`, matching the existing card language

```swift
Picker("Ulaşım Modu", selection: transportModeBinding) {
    ForEach(OptimizerTransportMode.allCases, id: \.self) { mode in
        Label(mode.title, systemImage: mode.symbolName)
            .tag(mode)
            .accessibilityLabel(mode.accessibilityLabel)
    }
}
.pickerStyle(.segmented)
```

wrapped in the same `AppColors.surface` card / `RoundedRectangle(cornerRadius: 16)`
/ `AppColors.border` overlay the duration and planning-time cards already
use, placed directly below the planning-time card and above the bottom
spacer — no restructuring of the existing section order. `mode.title`
("Araba"/"Yürüyüş") and `mode.symbolName` (`car.fill`/`figure.walk`) both
already existed on `OptimizerTransportMode` since v12 — nothing was
duplicated as a raw string or a new icon mapping. A native SwiftUI
`Picker` with `.segmented` style was used rather than a custom control,
per the milestone's own preference and consistent with every other
control on this screen (`Toggle`, `DatePicker`) already being native.

### Restoration and persistence: inherited, not reimplemented

Nothing about restoration changed. `TripOptimizerConfigViewModel.init`
already restores `transportMode` from `OptimizerConfigurationStore`
synchronously (v15) — the picker just reflects whatever that restore
produced, with no additional loading state. Nothing about persistence
changed either: `setTransportMode` already wrote through to the store
(v15) and the store already handled trip-keyed isolation (v15) — the
picker is a new *caller* of pre-existing, already-tested behavior.

### Map consistency — proven, not newly implemented

The full loop described in the milestone (config → Yürüyüş → generate →
map opens in Yürüyüş → map → Araba → reopen config → config shows
Araba) was already the union of v15 restoration + v16 sync, now with a
second observable UI on the config side. No new synchronization
mechanism was added — `OptimizerConfigurationStore.updateTransportMode`
(v16) and `configStore.configuration(for:)?.transportMode` (v15, read by
`TripOptimizerView` to seed the map) are untouched.

### Testing

`TripOptimizerConfigViewModelTests.swift` gained ten focused tests:
default mode is `.automobile`; `setTransportMode(.walking)` and
`setTransportMode(.automobile)` each update `vm.transportMode` directly
(previously only exercised indirectly, through the stored configuration);
a value set via the ViewModel is readable from
`OptimizerConfigurationStore.configuration(for:)?.transportMode` exactly
the way `TripOptimizerView` reads it to seed the map's
`initialTransportMode`; changing transport mode leaves selected places,
duration, preferred start/end time, and preferred start date all
provably unchanged (one test per field); and two explicit three-visit
trip-isolation round trips — Trip A → Yürüyüş, Trip B → Araba, reopen
Trip A → still Yürüyüş; and the inverse, Trip A → Araba, Trip B →
Yürüyüş, reopen Trip A → still Araba.

`TripOptimizerConfigView.swift`/`OptimizerRouteMapSection.swift` are
SwiftUI `View`s and, per this project's established convention, are not
unit-tested directly. The v16 map-side persistence tests
(`OptimizerConfigurationStoreTests.swift`'s `updateTransportMode` suite)
were not touched and passed unmodified, confirming the picker's addition
didn't disturb that path.

### Scope boundaries (explicitly out of scope for this milestone)

Transit, new transport types, route styling, cross-app-launch
persistence, server-side transport-mode persistence, a map redesign, new
optimizer strategies, date/timezone changes, itinerary editing, and any
route-cache changes — none of that changed here.

## Transit Transport Mode

Adds `.transit` — Toplu Taşıma, 🚋 `tram.fill` — as `OptimizerTransportMode`'s
third case, alongside `.automobile`/`.walking`.

### Architecture/design decision: extend one enum, change nothing else

Every layer that touches transport mode — `OptimizerRouteCalculator`'s
`cacheKey`/`legKey`, `OptimizerRouteCache`'s storage (an opaque
`[String: [CLLocationCoordinate2D]]`, no awareness of mode at all),
`OptimizerConfiguration`/`OptimizerConfigurationStore` (mode is just a
stored `OptimizerTransportMode` value), and both selector UIs
(`TripOptimizerConfigView.transportModeSection`,
`OptimizerRouteMapSection.transportModeSelector`) — was already written
generically against `OptimizerTransportMode.allCases` and
`mode.rawValue`, not against a hardcoded `.automobile`/`.walking` pair.
This was confirmed by inspection (per this milestone's own Req 1) before
any code was touched, and directly explains why the entire cache
correctness / persistence / restoration surface (Reqs 6, 7) required
**zero** production changes outside the enum itself, the routing
provider's one-line mapping, and a small UI scroll-affordance fix.
`OptimizerConfiguration`/`OptimizerConfigurationStore`/`OptimizerRouteCache`
were not modified at all.

### Enum changes

```swift
enum OptimizerTransportMode: String, CaseIterable, Hashable, Sendable {
    case automobile
    case walking
    case transit   // new

    var title: String { … "Toplu Taşıma" for .transit … }
    var accessibilityLabel: String { … "Toplu taşıma rotası" … }
    var symbolName: String { … "tram.fill" … }
    var mapKitType: MKDirectionsTransportType { … .transit … }
}
```

`rawValue` is `"transit"` — stable, matches the naming convention of
`"automobile"`/`"walking"`. All four display/mapping properties stayed
centralized on the enum (Req 2 "do not hardcode transport-mode labels
throughout the UI") — neither selector UI gained a new string literal or
icon mapping; both already iterate `allCases` and read `title`/`symbolName`/
`accessibilityLabel` generically, so the third case appeared in both UIs
automatically.

### MKDirections integration

`MKDirectionsRoutingProvider.route(from:to:mode:)` — the sole place
`MKDirectionsTransportType` is read anywhere in the codebase — required
no change beyond what `mode.mapKitType` already provided:
`request.transportType = mode.mapKitType` now naturally receives
`.transit` when `mode == .transit`. `MKDirectionsTransportType` still
does not leak into SwiftUI, ViewModels, the cache, the calculator, or any
configuration/domain model (Req 3) — confirmed by grep, unchanged from
v12.

### Transit availability / failure semantics

Nothing new was built here — the existing (v6) partial-failure model
already does exactly what Req 4 asks for, and now covers transit for
free:

- A leg's `MKDirections.calculate()` throwing (no route found —
  expected and common for transit, given regional/schedule/coverage
  limits) is caught in `OptimizerRouteCalculator.load`'s per-leg loop,
  produces a straight-line `OptimizerRouteSegment(isRoaded: false)`, and
  is **never** written to `OptimizerRouteCache` — so the next visit (or
  request) retries automatically.
- A day with some successful and some failed transit legs still renders
  every stop and every leg — successful legs as real geometry, failed
  ones as straight lines — never a missing segment, never a crash.
- No new error UI was introduced; the pre-existing dashed-line rendering
  (`OptimizerDayPolyline.isRoaded == false` → `lineDashPattern`, in
  `OptimizerRouteMap`) already communicates "this segment is a fallback"
  for any mode, transit included.

### Transit-specific request configuration — investigated, deliberately not added

`MKDirections.Request` supports `departureDate`/`arrivalDate`, which can
affect transit results (schedule-aware routing). `OptimizerRoutingProviding.route(from:to:mode:)`
has no time parameter, and the optimizer's `planningDate`/`preferredStartTime`/
`preferredEndTime` do not reach `MKDirectionsRoutingProvider` at all —
threading them through would require changing the routing protocol, the
calculator's cache-key shape (a departure time would need to become part
of leg identity, or cached transit results would silently go stale
across different planned times), and the call sites that currently don't
carry a timestamp anywhere. That is a materially larger, separately
scoped piece of work (a genuine "transit scheduling" milestone), not a
small addition — so, per this milestone's own instruction ("prefer the
smallest correct integration... document the limitation rather than
introducing hidden time assumptions"), no departure/arrival date is set.
`MKDirections` falls back to its own default ("route as if departing
now"). This is documented explicitly in `MKDirectionsRoutingProvider`'s
own doc comment and repeated here:

> Transit routing is availability-dependent and may fall back to
> straight-line visualization when MKDirections cannot provide a transit
> route for the current request/context. Transit route geometry, when
> found, reflects "depart now," not the optimizer's own planned day/time
> — this is not a schedule-aware, timetable-integrated transit
> itinerary.

### Cache correctness (verified, not redesigned)

`cacheKey`/`legKey` both include `mode=<rawValue>` — a plain string
interpolation with no enumeration of specific cases — so `mode=transit`
is automatically a distinct cache namespace from `mode=automobile`/
`mode=walking`, with no code change. Verified with:

- `test_cacheKey_transitDiffersFromAutomobile` /
  `test_cacheKey_transitDiffersFromWalking` — structural key inequality.
- `test_transportModeCache_walkingThenTransit_switchingDoesNotReuseWalkingRoute` /
  `test_transportModeCache_transitThenAutomobile_switchingDoesNotReuseTransitRoute` —
  switching modes always issues a fresh request, never silently reuses
  another mode's cached geometry.
- `test_transportModeCache_allThreeModesCoexist_inSameSharedCache` —
  written generically over `OptimizerTransportMode.allCases` (not
  hardcoded to three literal cases), so it automatically re-verifies this
  guarantee if a fourth mode is ever added: all modes are computed once,
  then a brand-new calculator sharing the same `OptimizerRouteCache`
  retrieves every mode synchronously from cache with zero new requests.
- `test_transitCache_failedRequest_isNeverCached` — a failed transit leg
  never enters the cache, mirroring the pre-existing automobile/walking
  guarantee.

No entire-cache clear occurs on a mode switch — only the current day's
*displayed* route resets to a loading/straight-line state (existing v12
behavior, `OptimizerRouteCalculator.load`), while every other day's and
every other mode's cached entries are untouched.

### Configuration persistence

`OptimizerConfiguration.transportMode: OptimizerTransportMode` and
`OptimizerConfigurationStore` store/restore the enum value opaquely —
neither needed a code change to support a third case. The full loop
described in the milestone spec (config → Transit → generate → map opens
in Transit → map → Walking → reopen config → config shows Walking, trip
A/B isolation throughout) is the same v15/v16/v17 machinery, now
exercised with `.transit` instead of `.walking` in
`TripOptimizerConfigViewModelTests.swift`'s new Transit-specific tests
(default remains `.automobile`, Transit selects/persists/restores, trip
isolation, and non-interference with places/duration/time/date) and
`OptimizerConfigurationStoreTests.swift`'s
`test_updateTransportMode_toTransit_worksExactlyLikeOtherModes` (the
map-sync path from v16).

### Configuration UI

`TripOptimizerConfigView.transportModeSection`'s segmented `Picker`
iterates `OptimizerTransportMode.allCases` — Transit appeared as a third
segment automatically, no card/layout code changed. A native
`.pickerStyle(.segmented)` `Picker` was kept (not replaced with a custom
control) — Apple's own Maps app uses exactly this pattern (a 2-3 option
segmented transport picker with `Label(_:systemImage:)`), and SwiftUI's
segmented control already handles narrower per-segment width reasonably
at three options.

### Map transport selector

`OptimizerRouteMapSection.transportModeSelector` also iterates
`allCases` — Transit appeared automatically, driving the exact same
`selectedTransportMode` `@State` that already controls
`OptimizerRouteCalculator.load(day:mode:)` (Req 9). One adjustment was
made: the selector's doc comment previously justified skipping a
`ScrollView` wrapper specifically because there were "only 2 options";
that premise is no longer true, so the chip row was wrapped in the same
horizontal `ScrollView` `daySelector` already uses elsewhere in this
file — the smallest change that keeps three chips usable on narrow
devices without altering the chip design itself. Selecting Transit
follows the existing, unmodified v12 lifecycle exactly: the previously
displayed route is replaced immediately with a straight-line + loading
state, a fresh calculation starts (or a cache hit renders synchronously
if already computed for that day/mode), and no other mode's cache
entries are cleared.

### Route rendering

Unmodified. `OptimizerRouteMap` still renders any `OptimizerRouteSegment`
generically by `isRoaded` (solid vs. dashed) — it has no notion of
transport mode at all, and none was added. A successful transit `MKRoute`
renders exactly like a successful automobile/walking route.

### Testing

25 new tests, deterministic and provider-mocked throughout (no live
`MKDirections`/network dependency in the core suite, per this
milestone's own instruction):

- `OptimizerTransportModeTests.swift` (+5, and one existing test renamed):
  transit title/symbol/accessibility-label/raw-value/MapKit-mapping, and
  `test_allCases_containsExactlyAutomobileAndWalking_noTransit` →
  `test_allCases_containsAutomobileWalkingAndTransit_inThatOrder` (a
  deliberate contract change, not a bug — the old test explicitly
  asserted transit's *absence*, which this milestone's entire purpose is
  to end).
- `OptimizerRouteCalculatorTests.swift` (+9): cache-key inequality
  (vs. automobile, vs. walking), the mode reaching the fake provider as
  `.transit`, synchronous cache-hit reuse, failed-request non-caching,
  partial-failure leg preservation, both switching directions
  (walking→transit, transit→automobile) never reusing the wrong mode's
  route, and the generic three-mode coexistence test.
- `TripOptimizerConfigViewModelTests.swift` (+10): default-still-automobile,
  select/persist/restore, trip isolation, store-readability (mirroring
  how the map reads it), and four non-interference tests (places/
  duration/time/date).
- `OptimizerConfigurationStoreTests.swift` (+1): `updateTransportMode`
  (the v16 map-sync path) works identically for `.transit`.

### Simulator / live verification

Live `MKDirections` transit routing was **not** exercised — this
environment has no authenticated backend session or real trip data to
reach the optimizer screens interactively, and transit coverage/data
availability cannot be guaranteed or meaningfully asserted from a
Simulator smoke test even if it were reached. Per this milestone's own
guidance ("if transit data is unavailable... verify the failure/fallback
path instead"), the failure/fallback path was verified deterministically
instead, via `FakeOptimizerRoutingProvider` — `test_transitCache_failedRequest_isNeverCached`
and `test_transitPartialFailure_preservesSuccessfulLegs` exercise exactly
the code path a real "no transit route available" response would take. A
plain install/launch/screenshot check confirmed the enum change doesn't
crash app startup. This is an honestly-reported environment limitation,
not a weakened test or a claimed-but-unverified success.

### Scope boundaries (explicitly out of scope for this milestone)

Full transit timetable optimization, multi-modal routes, bus/train
transfer optimization, any external transit provider API (Google Maps
Transit, etc.), transit-specific route rendering/styling, cross-launch
persistence, backend/BFF changes, new optimizer strategies, new
itinerary-editing behavior, and date/timezone redesign — none of that
changed here.

## Delete Saved Itinerary

Adds real backend deletion of a saved `TripItinerary` from
`ItineraryHistoryView` — the first *destructive*, *mutating* operation
this history screen has ever had (every prior milestone here was
read-only or additive). Full stack: `ItineraryHistoryView` (swipe +
confirm) → `ItineraryHistoryViewModel.deleteItinerary` → Mobile BFF
`DELETE /api/mobile/itineraries/{id}` → core-api
`DELETE /internal/itineraries/{id}` → PostgreSQL. See
`docs/trip-optimizer.md` "`DELETE /internal/itineraries/{itinerary_id}`"
for the full backend contract (permissions, cascading behavior, the
applied-itinerary reference, why deletion is explicit rather than
DB-cascade-only).

### Architecture/design decision: extend, don't invent

Every layer reused an existing, directly-analogous pattern rather than
inventing a new one:

- **Core-API**: `SqlOptimizationRepository.delete_itinerary` mirrors
  `SqlTripRepository.delete_trip`'s own "explicit child-row cleanup, not
  DB-cascade-reliant" pattern almost line for line (see that method's own
  comment about SQLite not enforcing `ON DELETE` actions without
  `PRAGMA foreign_keys=ON`). `OptimizationService.delete_itinerary` reuses
  `ItineraryNotFoundException` — no new exception type.
- **Mobile BFF / Web BFF**: `DELETE /itineraries/{id}` is a direct proxy,
  same shape as the existing `apply_itinerary` proxy in the same file —
  authenticate, forward to core-api with `x-user-id`, propagate
  status/error, no business logic. Web BFF got the same endpoint too (see
  "Web BFF parity" below) — its `trip_optimization.py` already mirrors
  Mobile BFF's `optimize`/`list`/`get`/`apply` 1:1 for API-parity reasons
  stated in that file's own doc comment, so delete followed the same
  convention rather than being iOS-only at the BFF layer.
- **iOS**: `Endpoint.deleteItinerary` sits alongside the existing
  `.deleteTrip`/`.deletePlan` cases; `ItineraryHistoryViewModel.deleteItinerary`
  follows `TripDetailViewModel.deleteTrip`'s exact shape (a
  `SuccessResponse`-typed `send`, re-entrancy guard, error string
  property); the UI reuses `TripDetailView`'s own
  `.confirmationDialog(title, isPresented:, titleVisibility: .visible) { "Sil"/"Vazgeç" }`
  destructive-confirm convention verbatim, and `HistoryView.swift`'s
  (the Core Data video-history screen) own `.swipeActions(edge: .trailing, allowsFullSwipe: true)`
  pattern — proof, already shipping elsewhere in this app, that
  `.swipeActions` works correctly inside a `ScrollView`+`LazyVStack` (not
  only inside `List`), so `ItineraryHistoryView.list` did not need to be
  rebuilt around `List` to get native swipe-to-delete.

No new global singleton, no bypass of the Mobile BFF, no new persistence
mechanism, no local/optimistic-only deletion — the row is removed from
the displayed list only after the backend confirms success.

### Backend: anti-enumeration stricter than `apply`

`OptimizationService.delete_itinerary` maps **both** `"not_found"` and
`"forbidden"` (a non-owner/non-editor — including a viewer who legitimately
has *some* access to the trip) to the same `ItineraryNotFoundException`
(404). This is a deliberate divergence from `apply_itinerary`, which
returns `403 PERMISSION_DENIED` for a viewer and `404 ITINERARY_NOT_FOUND`
for a true outsider — a distinction that lets a caller infer an itinerary
exists even without access to it. Delete's anti-enumeration requirement
was explicit and non-negotiable in this milestone's spec, so it collapses
that distinction; `apply`/`get`/`list` were **not** changed to match — this
milestone only touched delete.

### Cascading behavior — explicit, not DB-cascade-reliant

`TripItineraryStop.itinerary_id` (`ON DELETE CASCADE`) and
`Trip.applied_itinerary_id` (`ON DELETE SET NULL`) both already had the
correct foreign-key actions declared in the schema, from the very
migrations that created these columns — `Trip.applied_itinerary_id`'s own
model doc comment explicitly anticipated this: *"itinerary ileride
silinebilir bir özellik kazanırsa Trip bundan etkilenmemeli, yalnızca 'son
uygulanan' işaretçisini kaybetmeli"* ("if the itinerary later gains a
deletable feature, the Trip shouldn't be affected by it, only lose its
'last applied' pointer"). **No migration was needed for this milestone** —
confirmed by inspecting the actual foreign keys before writing any code,
per the milestone's own Req 1.

However, this project's test suite runs against SQLite, which does not
enforce `ON DELETE` actions without an explicit `PRAGMA foreign_keys=ON`
this codebase never sets (confirmed by `apply_itinerary`'s own repository
code — a comment there documents an earlier bug caused by trusting
SQLite's FK enforcement that never actually happened in tests). So
`delete_itinerary` deletes `TripItineraryStop` rows and clears
`Trip.applied_itinerary_id`/`itinerary_applied_at` **explicitly**, in
application code — correct and identical in both SQLite (tests) and
Postgres (production), not relying on environment-specific DB behavior.
`TripStop` (the trip's canonical, currently-active stops) and `Place` rows
are never touched by any code path here.

### iOS: swipe-to-delete, reusing the existing confirm/alert conventions

`ItineraryHistoryView.list`'s `NavigationLink` rows gained
`.swipeActions(edge: .trailing, allowsFullSwipe: true)` with a single
destructive "Sil" action, which sets `itineraryPendingDeletion` (an
`ItinerarySummary?`, not a bare `Bool` — so the confirmation dialog's
message can name *which* itinerary, satisfying the milestone's "clearly
identify the itinerary being deleted" requirement via
`summary.formattedCreatedAt`). Confirming calls
`vm.deleteItinerary(id:auth:)`; a row mid-deletion is dimmed
(`.opacity(0.5)`) and disabled, mirroring `TripOptimizerView.applyButton`'s
own "in-flight" visual language rather than inventing a new loading
indicator. A failed delete surfaces through a `.alert("Silinemedi", ...)`
bound to `vm.deleteError`, matching `TripOptimizerView`'s existing
"Uygulanamadı" alert pattern exactly.

### `ItineraryHistoryViewModel.deleteItinerary`

```swift
private(set) var deletingID: Int?
var deleteError: String?

@discardableResult
func deleteItinerary(id: Int, auth: AuthEnvironment) async -> Bool {
    guard deletingID == nil else { return false }   // re-entrancy guard
    guard let token = auth.user?.token else { return false }
    deletingID = id
    defer { deletingID = nil }

    do {
        let _: SuccessResponse = try await auth.apiClient.send(.deleteItinerary(itineraryID: id), token: token)
        itineraries.removeAll { $0.id == id }
        return true
    } catch let apiError as APIError {
        if apiError.isUnauthorized { auth.handleUnauthorized(); return false }
        deleteError = apiError.localizedDescription
        return false
    } catch {
        deleteError = "Silinemedi."
        return false
    }
}
```

`deletingID: Int?` does double duty — it's both the re-entrancy guard
(non-`nil` means a delete is already in flight, so a second call, from
any row, is a no-op) and the per-row "which row is busy" signal the View
reads to dim/disable that specific row. On success, `itineraries.removeAll { $0.id == id }`
removes only the deleted item — the rest of the array, and therefore its
order, is untouched, so no `load()`/full-reload is needed (Req "do not
unnecessarily reload the entire screen if local removal is sufficient").
On failure, `itineraries` is never mutated — the row simply stays, and
`deleteError` carries the message for the alert. `emptyState` (already
gated on `vm.itineraries.isEmpty`) appears automatically once the last
item is removed — no new empty-state logic was needed.

### Handling a currently-open saved itinerary

The milestone asked for this to be inspected explicitly. On this app's
linear, push-based `NavigationLink` stack, a user cannot be viewing
`TripOptimizerView(.viewSaved(itineraryID:))` for itinerary X **and**
simultaneously swiping to delete row X on `ItineraryHistoryView` — the
detail screen, once pushed, fully covers the list beneath it, so the two
interactions can never race on this navigation architecture. The
realistic scenario is: the user backs out to History (deallocating the
detail screen) and *then* deletes a row — already correctly handled by
`itineraries.removeAll` before any re-navigation is possible.

The one scenario that genuinely can happen — reaching a
`TripOptimizerView(.viewSaved(itineraryID:))` for an itinerary that was
*already* deleted (e.g., a second device deleted it, or a stale deep
link) — was **already** handled before this milestone: `TripOptimizerViewModel.loadItinerary`
already surfaces any `APIError` (including the new 404) through `vm.error`,
and `TripOptimizerView.body` already renders `errorState(_:)` (with a
"Tekrar Dene" retry) whenever `vm.error != nil`. No new code was needed
for this path — it's exercised by the existing, unmodified
`test_loadItinerary_serverError_setsError` test plus the new backend
404 behavior.

"Cannot remain selected/reopened through stale UI state" is satisfied by
the same mechanism: once `itineraries.removeAll` runs, the deleted row's
`NavigationLink` no longer exists in the list — there is no way to tap
into it again from `ItineraryHistoryView`. `OptimizerSelectionStore`/
`OptimizerRouteCache` may retain small, harmless orphaned entries keyed by
the deleted itinerary's id (bounded by the route cache's existing LRU
capacity) — they are simply never read again, since nothing can navigate
back to that itinerary. `OptimizerConfigurationStore` is keyed by `Trip.id`,
not itinerary id, so it's entirely unaffected by deleting one itinerary.

### Web BFF parity

`services/web-bff/app/routes/trip_optimization.py` already mirrors Mobile
BFF's `optimize`/`list`/`get`/`apply` 1:1, for the API-parity reason
stated in that file's own doc comment ("web de owner/editor akışının
tamamını görür" — as of v21, a web UI now calls all of this, see
`docs/web-trip-optimizer.md`).
`DELETE /itineraries/{id}` was added there too, for the same reason —
inspected first, per the milestone's own instruction, rather than added
reflexively.

### Testing

**Core-API** (`test_trip_optimization.py`, +13 tests): happy path (200,
row gone from DB); removed from `list_itineraries`; child
`TripItineraryStop` rows deleted; `TripStop`/`Place` untouched; a second
itinerary on the same trip untouched (both its row and its own stops);
nonexistent itinerary → 404; cross-user (no trip access at all) → 404,
itinerary untouched; **viewer** (has trip access, not owner/editor) → 404
— not 403, proving the stricter anti-enumeration — itinerary untouched;
editor can delete; auth required; deleting the *applied* itinerary clears
`Trip.applied_itinerary_id`/`itinerary_applied_at` while leaving the
already-applied canonical `TripStop`s untouched; deleting a
*non-applied* itinerary while a *different* one is applied leaves
`applied_itinerary_id` pointing at the still-applied one, unaffected.

**Mobile BFF / Web BFF** (`test_trip_optimization.py`, +5 each): auth
required, happy-path forwarding (correct upstream URL, `x-user-id`
header, body passthrough), 404 propagation, 500/upstream-error
propagation, core-api-unreachable → 503. Discovered along the way: Web
BFF's `error_wrapper._parse_core_error` remaps `INTERNAL_SERVER_ERROR` to
`503` (not `500`, unlike Mobile BFF) and returns `401` (not `403`) for
missing auth — both **pre-existing, unrelated-to-this-milestone**
behaviors that an initial 1:1 copy of the Mobile BFF tests got wrong; the
web-bff tests were corrected to match actual (and correct) existing
behavior rather than the assumption. `web-bff`'s `mock_core_api` fixture
gained `.delete` mocking (previously only `.get`/`.post` — this was the
first `DELETE` proxy web-bff ever had), matching Mobile BFF's fixture
shape exactly.

**iOS** (`ItineraryHistoryViewModelTests.swift`, +10): successful deletion
removes the correct row; ordering of remaining rows is preserved; a
failed deletion leaves the row intact with `deleteError` set; double
submission (a second call while the first is still in flight, verified
via `AsyncGate`) is ignored; deleting one itinerary doesn't alter the
others (`Equatable`-compared before/after); deleting the last remaining
entry empties the array (driving `emptyState`); a failed delete can be
retried and succeeds; unauthorized clears the session without setting
`deleteError`, and never removes the row; no token means the API is never
called; and a two-ViewModel trip-isolation test (each `ItineraryHistoryViewModel`
only ever represents one trip's own list, so deleting in one has zero
effect on the other's array).

### Regression

Core-API: 503/503 (full suite). Mobile BFF: 107/107. Web BFF: 64/64. iOS:
299/299, clean build, no new warnings. No unrelated files changed; no
optimizer algorithm, route-cache, or transport-mode behavior touched.

### Scope boundaries (explicitly out of scope for this milestone)

Full timetable/apply-history features, bulk delete, undo/restore,
soft-delete, a second history screen or duplicate row UI, backend/BFF
business-logic changes beyond the delete operation itself, and any
optimizer-algorithm/route-cache/transport-mode changes — none of that
changed here.

## Apply History & Undo

Adds a durable log of every successful "Trip'e Uygula"/"Geri Al" action,
and a safe way to undo the most recent one — closing the exact gap called
out as the recommended next milestone at the end of "Delete Saved
Itinerary." Full backend contract (data model, snapshot semantics,
latest-only safety rule, deletion interaction, analytics) is in
`docs/trip-optimizer.md` "Apply History & Undo" — this section covers the
iOS-specific architecture/UI/testing.

### Architecture/design decision: a new, screen-scoped ViewModel — nothing forced into existing ones

`TripOptimizerViewModel` already owns "apply" (`applyToTrip`); it was
**not** extended with undo/history-list responsibilities — those belong to
a genuinely different screen (a trip-scoped log, not a single itinerary's
apply action), and stuffing them in would have coupled two unrelated
concerns into one ViewModel (Req 9's own explicit instruction: "do not
force unrelated responsibilities into TripOptimizerViewModel"). Instead,
`ItineraryApplyHistoryViewModel` was added, following
`ItineraryHistoryViewModel`'s established skeleton exactly (re-entrancy
guard, `isLoading`/`error` pair, 401 → `auth.handleUnauthorized()`) — the
same precedent that justified a *separate* ViewModel for Itinerary
History rather than folding it into `TripDetailViewModel`.

### `ItineraryApplyHistoryViewModel`

```swift
private(set) var entries:   [ApplyHistoryEntry] = []
private(set) var isLoading  = false
private(set) var error:     APIError?

func load(tripID: Int, auth: AuthEnvironment) async { … }

private(set) var undoingID: Int?
var undoError: String?

@discardableResult
func undo(historyID: Int, tripID: Int, auth: AuthEnvironment) async -> Bool { … }
```

`undoingID: Int?` does the same double duty `ItineraryHistoryViewModel.deletingID`
established: it's both the re-entrancy guard (non-`nil` ⇒ a second `undo()`
call, from any row, is a no-op) and the per-row "which entry is busy"
signal the View reads to dim/disable that specific row.

**`undo()` deliberately does *not* call `load()` internally.** An earlier
version did, on the reasoning that "the server is authoritative, so
auto-refresh after a successful undo." That turned out to be
untestable with this project's existing `FakeAPIClient`: it holds a
single, statically-typed `result` for the *entire* test, and `undo()`
returning `UndoApplyResult` followed immediately by an internal `load()`
expecting a differently-shaped `ApplyHistoryListResponse` would force the
same fake value through two incompatible casts — the second `send` call
would `fatalError`. Rather than extend `FakeAPIClient` into a
per-call-type response queue (a bigger, riskier change to shared test
infrastructure used by every other test file), `undo()` was kept to a
single API call — matching `deleteItinerary`'s own "one method, one
network call" shape — and the reload was moved to the caller
(`ItineraryApplyHistoryView`, which already orchestrates the confirmation
flow):

```swift
Task {
    let success = await vm.undo(historyID: entry.id, tripID: tripID, auth: auth)
    if success {
        await vm.load(tripID: tripID, auth: auth)   // sunucu otorite — yerel tahmin yok
        onChanged?()                                  // TripDetailView'i de yenile
    }
}
```

The net behavior — "the server is authoritative, the list always reflects
a fresh fetch after a successful undo, never a local guess" (Req 10's own
explicit requirement) — is identical either way; only *which layer* issues
the second call changed, and the result is a more testable, single-purpose
ViewModel method.

### iOS models

`ApplyHistoryEntry`/`ApplyHistoryListResponse`/`UndoApplyResult` mirror
core-api's `ApplyHistoryEntryResponse`/`ApplyHistoryListResponse`/
`UndoApplyResponse` field-for-field (via `APIClient`'s existing
`.convertFromSnakeCase` decoder, same as every other model in this file).
`ApplyHistoryEntry.itineraryId: Int?` and `.itineraryCreatedAt: String?`
are both optional — the same "either undo restored a non-itinerary state,
or the itinerary was later deleted" ambiguity core-api's own docs describe
(see `docs/trip-optimizer.md`); the two cases are disambiguated in the UI
by also reading `isUndo` (see row view below), not by adding a new field.

### UI: a new toolbar entry point, not a redesign

`TripDetailView` gained a **third** toolbar icon (`arrow.uturn.backward.circle`),
alongside the existing "sparkles" (Optimize) and "clock.arrow.circlepath"
(Itinerary History) — gated on a new `TripDetailViewModel.hasApplyHistory`
flag, refreshed by a new best-effort `refreshApplyHistoryFlag(tripID:auth:)`
method. Both are a direct copy of the existing
`hasItineraryHistory`/`refreshItineraryHistoryFlag` pattern (a separate,
parallel `.task` that never blocks or slows the trip's own load, and fails
silently to `false` rather than surfacing an error for what is genuinely
non-critical UI chrome) — no new pattern was invented. This inherits that
pattern's one known, pre-existing limitation too: neither flag is
re-checked after `onApplied`/`onChanged` fires (only `vm.load(tripID:...)`
is called) — so a *first-ever* apply's history entry doesn't make the
toolbar icon appear until the screen is next freshly mounted. This isn't
new to this milestone; it was already true for `hasItineraryHistory`, and
fixing it was out of scope here (see "Known limitations" below).

### `ItineraryApplyHistoryView`

Same four-state skeleton (`loading`/`error`/`empty`/`list`) every other
list screen in this file uses. Each row (`ItineraryApplyHistoryRowView`,
matching `ItineraryHistoryRowView`'s card layout exactly — leading badge +
two lines of meta) shows a checkmark badge for a normal apply, an
`arrow.uturn.backward` badge for an undo, a "Güncel" tag when
`entry.isUndoable`, and a title that disambiguates all four
`itineraryId`/`isUndo` combinations:

| `itineraryId` | `isUndo` | Title |
|---|---|---|
| set | `false` | "Itinerary uygulandı" |
| set | `true`  | "Önceki itinerary'e dönüldü" |
| `nil` | `false` | "Silinmiş optimizasyon" |
| `nil` | `true`  | "Manuel durak listesine dönüldü" |

Only the row where `entry.isUndoable == true` renders a "Geri Al" button
— never derived from "is this the first element in the list" (which would
duplicate server logic and could drift from it); always read directly
from the field the server computed. Confirming shows a
`.confirmationDialog` using this project's established destructive-confirm
convention verbatim (`TripDetailView`'s own trip-delete dialog: title +
"Sil"/"Vazgeç" → here, title + "Geri Al"/"Vazgeç"), with the milestone's
own suggested copy: *"Son optimizasyon uygulamasını geri almak istediğine
emin misin?"*. A row mid-undo is dimmed (`.opacity(0.5)`) and its button
disabled, matching `TripOptimizerView.applyButton`'s existing "in-flight"
visual language — no new loading indicator was invented. A failed undo
surfaces through a `.alert("Geri Alınamadı", ...)` bound to
`vm.undoError`, the same shape as `TripOptimizerView`'s existing
"Uygulanamadı" alert.

### `TripDetailView` refresh after undo

`ItineraryApplyHistoryView`'s `onChanged: (() -> Void)?` init parameter is
the same callback-bubbling shape `ItineraryHistoryView.onApplied`/
`TripOptimizerView.onApplied` already established — `TripDetailView` wires
it to `{ Task { await vm.load(tripID: tripID, auth: auth) } }`, so a
successful undo re-fetches and re-renders the trip's current stops (Req
12's own explicit requirement — "TripDetailView refreshes after Undo").
"Refresh optimizer state if currently visible" (also asked for in the
spec) was investigated and found to be unreachable on this app's linear,
push-based `NavigationStack`: a user cannot be viewing
`TripOptimizerView`/`TripOptimizerConfigView` and simultaneously
interacting with `ItineraryApplyHistoryView` (reached from a *different*
`TripDetailView` toolbar button) at the same time — the same reasoning
already documented for the equivalent "currently open" scenario in "Delete
Saved Itinerary → Handling a currently-open saved itinerary" above.

### Testing

**Core-API** (`test_trip_optimization.py`, +26 tests — including a genuine
bug caught and fixed, see below): apply-history creation on a successful
apply; newest-first ordering; only-latest-undoable; the complete previous-stop
snapshot recorded (not just place IDs — day/order too); exact `TripStop`
restoration after undo; `Trip.applied_itinerary_id` correctly updated
(and correctly cleared to `None` when the restored state predates any
itinerary); the `409 STALE_UNDO` conflict rejecting a non-latest undo
attempt with zero mutation; a new history row created by undo itself;
**undo-of-undo behaving as a redo** (see `docs/trip-optimizer.md` "Why
this symmetry matters"); the saved `TripItinerary` provably untouched by
undo; **deleting an itinerary does not destroy its apply-history entries**
(itinerary_id becomes `null`, the row survives); owner/editor/viewer/
outsider permission matrix for both list and undo; auth required;
nonexistent trip/history → `404`; a history row belonging to a *different*
trip → `404` (not leaked across trips); a failed apply creates no history
row; a failed undo (a snapshot referencing a since-deleted place) leaves
both `TripStop` and every history row byte-for-byte unchanged; the first
apply on a trip correctly has `previous_itinerary_id: None`; trip
isolation; and the `shared_trip_itinerary_apply_undone` analytics event
firing with the right payload.

**Mobile BFF / Web BFF** (`test_trip_optimization.py`, +10 each): auth,
happy-path forwarding for both `GET` history and `POST` undo, `404`
propagation, **`409` propagation** (required adding `STALE_UNDO`/
`APPLY_HISTORY_NOT_FOUND` to both BFFs' error-code → HTTP-status maps —
without this, a core-api `409` would have silently become a generic `400`
at the BFF, since both BFFs default unmapped codes to `400`), and
upstream-error/unreachable propagation. Web BFF's own `INTERNAL_SERVER_ERROR
→ 503` / missing-auth `→ 401` behaviors (documented as a *v19* finding)
were correctly anticipated this time — the new tests asserted the actual
behavior from the start, not a copy-pasted Mobile BFF assumption.

**iOS** (`ItineraryApplyHistoryViewModelTests.swift`, 16 new tests):
decoding/endpoint-forwarding for `load()`; server order preserved
as-given; only the server-flagged latest entry is undoable (never
client-derived); a deleted-itinerary entry decodes with `itineraryId: nil`;
empty history; network/401/no-token guards; `load()` re-entrancy; a
successful `undo()` clears `undoingID`/returns `true`; a failed `undo()`
sets `undoError`/returns `false`; `undo()` double-submission prevented
(via `AsyncGate`, mirroring `ItineraryHistoryViewModelTests`'s own
`deleteItinerary` re-entrancy test); 401/no-token guards for `undo()`; and
a two-ViewModel trip-isolation test (each `ItineraryApplyHistoryViewModel`
represents exactly one trip's log, per the screen's own `tripID`-scoped
design — no cross-trip leakage).

### A real bug found and fixed: delete didn't clear apply-history references

`DELETE /internal/itineraries/{id}` (v19) only explicitly cleared
`Trip.applied_itinerary_id`/`itinerary_applied_at` when deleting an
itinerary — it had no reason to know about apply-history rows, because
they didn't exist yet at the time it was written. Once this milestone
added `TripItineraryApplyHistory.itinerary_id`/`previous_itinerary_id`
(both `ondelete=SET NULL`, like `Trip.applied_itinerary_id`), the very
first run of `test_delete_itinerary_does_not_destroy_apply_history` failed
— SQLite doesn't enforce `ON DELETE` actions without `PRAGMA foreign_keys=ON`
(this codebase's now-familiar, repeatedly-encountered gap; see v19's own
"Why explicit deletion" section), so the row's `itinerary_id` stayed
pointing at the now-deleted itinerary instead of becoming `null`. Fixed by
extending `delete_itinerary`'s existing explicit-cleanup block to also
null out both apply-history FK columns, mirroring the exact pattern
already used for the trip's own pointer. Caught by a test written *before*
assuming the fix was needed — exactly the kind of interaction the
milestone's own "Important deletion semantics" section anticipated.

### Simulator / live verification

Live install/launch/screenshot: clean, unauthenticated launch screen, no
crash. The full interactive flow (apply → apply again → open Apply History
→ confirm "Geri Al" → row disappears from undoable state, TripDetailView's
stop list visibly reverts) was **not** exercised interactively — same
standing limitation as every prior milestone in this file (no XCUITest
harness, and reaching this screen requires a live backend + authenticated
session + a trip with at least one real apply). Covered instead by the
full four-suite regression below.

### Regression

Core-API: 529/529 (full suite; 503 carried over + 26 new). Mobile BFF:
117/117 (107 + 10 new). Web BFF: 74/74 (64 + 10 new). iOS: 315/315 (299 +
16 new), clean build, no new warnings, stable across repeated runs (one
single-run failure in an *unrelated*, untouched file —
`OptimizerRouteCalculatorTests` — was confirmed to be a pre-existing
timing flake, not a regression, via three consecutive clean reruns all
green). No unrelated files changed; no optimizer algorithm, route-cache,
or transport-mode behavior touched.

### Scope boundaries (explicitly out of scope for this milestone)

Full apply-history retention/pruning policy, a dedicated "Redo" UI
affordance (undo-of-undo already works mechanically, see above, but isn't
separately labeled), apply-history pagination, bulk undo, any
optimizer-algorithm/route-cache/transport-mode changes — none of that
changed here.

## Map Visualization

`TripOptimizerView`'s result state (both `.generate` and `.viewSaved`)
gained a map section, `OptimizerRouteMapSection`, rendered as the first
element of `resultContent` — same "map first" placement convention
`TripDetailView`/`ResultsView` already use for `TripMapView`. It is
**visualization only**: nothing about it calls `optimize`, mutates the
Trip, or touches the optimization algorithm — `GreedyDistanceStrategy` and
every backend route are byte-for-byte unchanged by this milestone.

### Why a new component instead of reusing `TripMapView`

The existing `TripMapView` (`Features/Results/Components/TripMapView.swift`,
used by `TripDetailView` and `ResultsView`) draws every location it's given
as **one continuous polyline**, in list order, with no concept of "day."
That's exactly right for a flat `TripStop`/`LocationPin` list, but wrong
here: an itinerary's stops are grouped into days, and connecting the last
stop of Day 1 to the first stop of Day 2 with a route line would draw a
real-looking line across a boundary the optimizer never actually
scheduled travel across (explicitly forbidden by this milestone's own
requirements). So this milestone adds three new, itinerary-specific types
in `Features/Trips/Components/` rather than bending `TripMapView` to a
shape it wasn't built for — but it deliberately **reuses `TripMapView`'s
own patterns** wherever they still apply (see below), rather than
inventing a new visual language:

- **`OptimizerRouteMapData`** — a pure, MapKit-free struct that converts an
  `Itinerary` into per-day, coordinate-only presentation data. No SwiftUI,
  no MapKit, no networking — just `Itinerary` in, `[OptimizerMapDay]` +
  a missing-coordinate count out. Exists specifically so the mapping logic
  is unit-testable without rendering an actual map (`OptimizerRouteMapDataTests`,
  13 tests, pure `XCTest`, no simulator needed for the assertions
  themselves).
- **`OptimizerRouteMap`** — the `UIViewRepresentable`/`MKMapView` wrapper.
  Copies `TripMapView`'s exact coordinator shape (pin annotation subclass,
  polyline overlay subclass, `MKMapViewDelegate` rendering, the
  "callout → Apple Maps" tap-to-open pattern, the min-span bounding-region
  fit formula) — the only real differences are day-colored, day-scoped
  overlays instead of one global one, and a numbered marker glyph per stop.
- **`OptimizerRouteMapSection`** — the SwiftUI-facing wrapper
  `TripOptimizerView` actually uses: computes `OptimizerRouteMapData` once
  (see "Performance" below), renders the day-selector chips, the map
  itself, and the missing-coordinate notice. `TripOptimizerView`'s
  `resultContent` calls this in one line
  (`OptimizerRouteMapSection(itinerary: itinerary)`); none of the mapping,
  filtering, or MapKit code lives in `TripOptimizerView` itself.

### Coordinates: already present, no backend/BFF change needed

Per this milestone's own instruction to only touch the backend "if the
existing itinerary response genuinely lacks coordinates required for
visualization" — it doesn't. `ItineraryStop.lat`/`lng` (nullable `Double`)
already existed in `Core/Models/OptimizerModels.swift` field-for-field with
core-api's `OptimizeTripResponse`, from the very first (`v1`) milestone —
see `docs/trip-optimizer-bff.md`. The map is built entirely from data the
client already receives; **no core-api, mobile-bff, or model change was
needed or made** for this milestone.

### Day separation (Req 2)

`OptimizerRouteMapData.init(itinerary:)` builds one `OptimizerMapDay` per
`ItineraryDay`, each carrying only its own stops. `OptimizerRouteMap` then
draws **one `MKPolyline` overlay per visible day**, connecting only that
day's own consecutive coordinates — there is no code path that ever
concatenates coordinates across two different `dayIndex` values into a
single overlay, so a Day 1 → Day 2 connecting line is structurally
impossible, not just avoided by convention.

Each day also gets its own marker color (a 5-color cyclical palette,
`OptimizerRouteMap.dayColors`, starting with the same route-teal
`TripMapView` already uses for day 1 / single-day itineraries, so a
one-day itinerary looks visually identical to before this milestone).

**Day selector**: for itineraries with more than one day,
`OptimizerRouteMapSection` shows a horizontal row of capsule chips ("Tümü"
+ one per day). Selecting a specific day sets
`OptimizerRouteMap.selectedDayIndex`, which does two things:
`OptimizerRouteMapData.visibleDays(selectedDayIndex:)` filters to just that
day's annotations/overlay, and the map re-fits its camera to that day's
stops only. Selecting "Tümü" shows every day at once, each in its own
color, still never connected to each other.

### Missing coordinates (Req 7)

`OptimizerRouteMapData.init` skips any `ItineraryStop` with a `nil` `lat`
or `lng` (this happens for a stop whose source `Place` was deleted after
the itinerary was generated — see `ItineraryStop`'s own doc comment on
`ondelete=SET NULL`) — it is never included in any day's `stops`, so it
can never reach `CLLocationCoordinate2D` construction or crash the map. No
coordinate is ever invented or geocoded client-side.

Two visible consequences, both required:
- **The stop stays visible in the textual itinerary.** `ItineraryDaySection`
  (the day/stop list below the map) is completely unmodified by this
  milestone — it renders every stop regardless of coordinates, exactly as
  before.
- **A non-blocking notice appears** when `OptimizerRouteMapData.missingCoordinateCount > 0`
  — small, secondary-colored text under the map ("N durağın konum bilgisi
  yok, haritada gösterilemiyor."), never an alert or blocking state. If
  *every* stop in the itinerary lacks coordinates, the map itself doesn't
  render at all (`OptimizerRouteMapData.isEmpty`) and only the notice
  shows — the rest of the result screen (score, warnings, day list, apply
  button) is completely unaffected either way.

Stop numbering is also missing-coordinate-aware: the marker glyph and
callout title show `stop.orderIndex + 1` — the optimizer's real,
server-assigned position — not a recount of only the plotted stops. If
stop 2 of 3 lacks a coordinate, the map shows "1" and "3", not "1" and
"2"; the gap is preserved rather than papered over, so the numbers on the
map always mean the same thing as `orderIndex` does everywhere else in
this feature.

### Route rendering limitation: straight lines, not roads (Req 6) — superseded by v6

> **Superseded by v6.** Everything in this subsection described v5's
> behavior at the time it shipped. As of v6 ("Real Road Route
> Visualization" below), segments are real `MKDirections` driving routes
> wherever one can be calculated — the straight-line behavior described
> here now applies only as v6's explicit per-segment *fallback*, not the
> default. Left intact below for historical accuracy.

**The polylines drawn between consecutive stops are straight geographic
segments between two coordinates — not driving/walking routes.** This
milestone calls no routing API (Apple's `MKDirections`, Google Directions,
or otherwise) — explicitly out of scope per this milestone's own
requirements. The line only visualizes *which order* the optimizer chose
to visit stops in, not *how* to physically travel between them. A
straight segment across, say, a body of water or a building is expected
and correct — it is not a claim about a real path, only the doc value
`travel_distance_to_next_km`/`travel_time_to_next_minutes` (shown
elsewhere in the day list, computed by `GreedyDistanceStrategy`) already
represent *estimated* straight-line-derived travel, not a routed one
either — the map is now visually consistent with a limitation the backend
already had.

### Saved itinerary behavior (Req 3)

The map makes **no distinction** between a freshly-generated result and
one reopened from Itinerary History — both are the same `Itinerary` value
flowing through the same `resultContent(_:)` → `OptimizerRouteMapSection(itinerary:)`
call in `TripOptimizerView`. Since `OptimizerRouteMapData` is a pure
function of an `Itinerary` value (see above), a `.viewSaved` itinerary
loaded via `loadItinerary` (`GET /itineraries/{id}`, never `POST
.../optimize`) produces an identical map to a `.generate` result with the
same stops — proven by
`OptimizerRouteMapDataTests.test_savedItineraryShape_mapsIdenticallyToFreshlyGeneratedItinerary`.
Viewing the map:
- **Never calls `optimize`** — `TripOptimizerViewModel.loadItinerary` is
  completely unmodified by this milestone; there is still no code path
  from `.viewSaved` to `POST /trips/{id}/optimize`.
- **Never mutates the Trip** — the map only reads `vm.itinerary`, already
  loaded; it has no write path of its own (the only Trip mutation
  anywhere in this feature remains the explicit "Trip'e Uygula" button,
  see "Apply to Trip" below, itself unmodified by this milestone).
- **Only renders the stored itinerary** — no new field is requested, no
  new endpoint is called; the map is built entirely from the `Itinerary`
  the existing `.itineraryDetail`/`.optimizeTrip` responses already carry.

### Interaction (Req 5)

Deliberately minimal, matching the "don't build a full navigation
experience" instruction:
- **Zoom/pan** — free, native `MKMapView` gestures; nothing here disables
  or intercepts them.
- **Tap a stop to identify it** — native MapKit annotation-select-and-callout
  behavior (`canShowCallout = true`), showing the stop's order + name and,
  for multi-day itineraries, which day it belongs to. No custom
  detail sheet or extra state was added for this — the callout alone
  satisfies "identify," same precedent as `TripMapView`.
- **Select a day to focus the map on that day's route** — the day-selector
  chips described above.
- **Apple Maps is only ever opened by an explicit tap** on a callout's
  "open in Maps" button (identical to `TripMapView`'s own behavior) —
  never automatically, never on annotation selection alone, matching
  the explicit "do not launch Apple Maps automatically" instruction.

No turn-by-turn navigation, no live location tracking, no route
recalculation UI — none of that was built, per scope.

### Performance (Req 9)

- `OptimizerRouteMapSection.mapData` is computed **once**, in the view's
  `init`, from the `itinerary` parameter — not recomputed on every SwiftUI
  `body` evaluation. Since `TripOptimizerViewModel.itinerary` is only ever
  assigned once per screen instance (the result of `optimize`/`loadItinerary`,
  never reassigned by `applyToTrip` — see "Apply to Trip"'s "byte-for-byte
  unchanged" guarantee), this mapping genuinely only needs to run once per
  screen visit.
- `OptimizerRouteMap.updateUIView` follows the same
  remove-then-readd-annotations/overlays approach `TripMapView` already
  uses in production — a deliberate consistency choice (same pattern,
  same file family) rather than a new risk; it only actually re-executes
  when SwiftUI detects a real prop change (`data` or `selectedDayIndex`),
  i.e. on initial load or an explicit day-chip tap, never on unrelated
  re-renders.
- The map's camera is only re-fit (`MKMapView.setRegion`) on the very
  first appearance and when `selectedDayIndex` actually changes
  (`Coordinator.lastSelectedDayIndex` gates this) — panning/zooming by the
  user is never overwritten by an unrelated state change, same
  "don't fight the user's own gesture" precedent `TripMapView` already
  established for its own `focusedPin` mechanism.

### Camera fitting (Req 8)

Reuses `TripMapView`'s exact bounding-region formula (min span 0.05°,
+40% padding around the coordinate spread) — already proven to handle a
single coordinate sensibly (falls back to the min span, since max−min is
0 for one point) and two coordinates correctly (spans exactly their
spread, padded). No itinerary-specific edge case was needed beyond what
`TripMapView` already handled, since day-scoped fitting just narrows the
coordinate set passed into the same formula.

## Real Road Route Visualization (MapKit Directions)

v5 shipped the map with straight geographic segments between consecutive
stops, explicitly documented as *not* real road geometry (see "Map
Visualization → Route rendering limitation" above). This milestone
replaces those segments with real `MKDirections` driving-route polylines
wherever MapKit can compute one, while preserving every architectural
boundary and behavioral guarantee v5 established — the straight-line path
still exists, now purely as the fallback for a segment MapKit can't route.

### Was `MKDirections` sufficient? Yes — with one necessary shape change

`MKDirections` reliably provides point-to-point driving route geometry
(`MKRoute.polyline`) and needs no new dependency, App capability, or
entitlement beyond what already ships (MapKit is already linked via
`TripMapView`/`OptimizerRouteMap`). **It does not, however, support
multi-waypoint routing in a single request** — an `MKDirections.Request`
takes exactly one `source` and one `destination`. A day's "Stop 1 → Stop
2 → Stop 3 → …" chain is therefore computed as **N−1 independent
pairwise requests** for N stops (Stop1→Stop2, Stop2→Stop3, …), each with
its own success/failure outcome — not one request for the whole day. This
is not a limitation that blocked the milestone; it's the correct native
shape for how `MKDirections` works, and it has a direct benefit: each leg
degrades independently (see "Fallback" below), so one un-routable segment
never takes the rest of the day's route down with it. No external
dependency was added or needed — this requirement was satisfiable
entirely within `MKDirections`.

### Architecture: where the new code lives

One new file, `Features/Trips/Components/OptimizerRouteCalculator.swift`,
holds everything MapKit-Directions-specific. The three v5 components keep
their exact original responsibilities (Req 4):

- **`OptimizerRouteMapData`** — completely unchanged. Still pure
  Foundation, still just `Itinerary` → per-day coordinate-only stops. It
  has no idea routes exist.
- **`OptimizerRouteMap`** — still the rendering layer, gained one new
  prop (`dayRoutes: [Int: OptimizerDayRoute]`, a plain value type — not
  the calculator itself) and now draws each day's segments individually
  instead of one whole-day polyline; it owns no async state, cache, or
  cancellation logic of its own.
- **`OptimizerRouteMapSection`** — still the SwiftUI orchestrator, and
  now also **owns** the new `OptimizerRouteCalculator` as `@State`
  (`@State private var calculator = OptimizerRouteCalculator()`),
  triggers route loading on day-selection change via
  `.task(id: selectedDayIndex)`, and cancels outstanding work via
  `.onDisappear { calculator.cancelAll() }`.

New types, all in `OptimizerRouteCalculator.swift`:

- **`OptimizerRoutingProviding`** — a one-method protocol
  (`route(from:to:mode:) async throws -> [CLLocationCoordinate2D]` — gained
  `mode:` in v12, see "Optimizer Route Transport Mode" below; originally
  `route(from:to:)`) that is the *only* seam between the calculator and
  `MKDirections`. This exists specifically because `MKRoute` has **no
  public initializer** — Apple's own type can only ever be produced by a
  real `MKDirections` call, which makes it impossible to construct a fake
  `MKRoute` for tests. Testing the protocol instead of the concrete
  MapKit type is what makes the orchestration logic testable at all (see
  "Testing" below).
- **`MKDirectionsRoutingProvider`** — the one production conformer;
  builds an `MKDirections.Request` (originally always `.automobile`
  transport, per Req 1's own "driving route geometry" wording; as of v12,
  `mode.mapKitType` — `.automobile` or `.walking`, whichever the user
  selected), awaits `MKDirections(request:).calculate()` (Swift's
  automatic async/await bridging over the completion-handler API — no
  manual continuation wrapping needed), and extracts the winning route's
  coordinates.
- **`OptimizerRouteCalculator`** (`@Observable @MainActor`, same
  ViewModel shape convention as `TripOptimizerViewModel`) — the
  orchestrator: per-day caching, per-day in-flight-request tracking,
  cancellation, and the synchronous straight-line-first/real-route-later
  state transition described below.
- **`OptimizerRouteSegment`** / **`OptimizerDayRoute`** — plain value
  types carrying the calculator's output (`isRoaded: Bool` per segment,
  `isLoading: Bool` per day) into `OptimizerRouteMap` without leaking any
  MapKit-Directions-specific type across that boundary.

### Route calculation behavior

`OptimizerRouteMapSection.loadVisibleDayRoutes()` calls
`calculator.load(day:)` for every currently-visible day whenever
`selectedDayIndex` changes (and on first appearance, since `.task(id:)`
fires once for the initial value too). For a given day, `load`:

1. **Single-stop day** — no pairs exist, so no request is ever made;
   `routes[dayIndex]` is set to an empty, non-loading state immediately.
2. **Cached** — if this exact day+stop-sequence was already resolved
   this screen visit, the cached segments are returned synchronously, no
   network call.
3. **Already in flight** — if the exact same day+key is already being
   computed (e.g. a repeated SwiftUI re-render calling `load` again
   before the first call finished), this is a no-op — the existing task
   is left running, never cancelled-and-restarted (Req 5, Req 6, Req 9;
   see `test_load_calledRepeatedlyWhileInFlight_doesNotRestartOrDuplicate`).
4. **Fresh** — `routes[dayIndex]` is set **synchronously** to the
   straight-line fallback for every leg, `isLoading: true`, so the map
   never shows an empty day while waiting. A `Task` is then spawned that
   requests each leg's route, in order, from the provider; each leg
   independently becomes either a real routed segment or a straight-line
   fallback (see "Fallback" below); once all legs resolve, the result is
   cached and written to `routes[dayIndex]`, `isLoading: false`.

### Day separation

Unchanged in spirit from v5, now reinforced structurally two ways: (1)
`OptimizerRouteMapData` still only ever gives the calculator one day's
stops at a time — there is no code path where a cross-day pair could even
be constructed; and (2) `routes` is keyed by `dayIndex`, so a day's
in-flight `Task` can only ever write to *that* day's entry — a Day 1
response completing after the user has already switched to Day 2 cannot
overwrite Day 2's displayed route, because it isn't writing to the same
dictionary key (Req 5 "a route response for Day 1 must never overwrite
Day 2's currently displayed route" — proven directly by
`test_daySwitching_bothDaysEndUpWithCorrectIndependentRoutes`). No
directions request's `source`/`destination` pair is ever built from two
different days' stops — proven by
`test_load_twoDays_neverRequestsAcrossDayBoundary`.

### Caching — superseded by v11

Keyed by `OptimizerRouteCalculator.cacheKey(for:)` — `"day=<index>|<stopID>@<lat>,<lng>|…"`
for every stop in that day, in order (Req 6's own "day + ordered stop
IDs/coordinates" wording, satisfied literally). Reordering, a different
day index, or a different stop set all produce a different key, so the
cache can never serve a stale sequence as if it were current. (`cacheKey`
gained an `itinerary=<id>` component in v11 — see "Persistent Optimizer
Route Cache" below.)

Within a single screen visit, the cache is exactly what prevents request
churn: switching from Day 1 → Day 2 → back to Day 1 only ever issues Day
1's requests once (see
`test_load_calledTwiceForSameDay_secondCallUsesCache_noNewRequests`), and
selecting "Tümü" after having already viewed individual days reuses every
day's already-cached result rather than re-requesting anything.

**Scope, as of v6: per-screen-instance, not persisted across app sessions
or re-opens.** `OptimizerRouteMapSection`'s `@State private var
calculator` was recreated whenever the section's own view identity was
recreated (a fresh `TripOptimizerView` navigation push), so reopening the
same itinerary recomputed every route from scratch. This was a deliberate
scope decision at the time (see "Known limitations" below, and v9/v10's
"Future UI improvements" lists) — **resolved in v11**, which added a
second, longer-lived cache layer (`OptimizerRouteCache`) that
`OptimizerRouteCalculator` also checks; see "Persistent Optimizer Route
Cache" below for the full design. This section's description of the
*day-level, screen-scoped* cache remains accurate for what happens
**within** one screen visit — v11 didn't remove or replace it, it added a
second, per-leg, longer-lived layer underneath it.

### Fallback behavior

If a leg's `MKDirections` call throws (no route found, e.g. across water
with no ferry/bridge connectivity that MapKit can route through; or a
network failure) — that leg, and only that leg, falls back to the
existing straight-line segment between its two coordinates. No crash, no
dropped stop, no dropped day (Req 3): the do/catch lives *inside* the
per-leg loop, so one failing leg doesn't abort the remaining legs of the
same day (see `test_load_partialFailure_otherSegmentsStillSucceed`).

The fallback state is made visible, but not disruptively: `OptimizerDayPolyline.isRoaded`
drives the overlay's `MKPolylineRenderer.lineDashPattern` — a real routed
leg draws **solid**, a straight-line fallback leg (whether because
`MKDirections` failed for that leg, or because the day's route hasn't
finished calculating yet) draws **dashed**, matching v5's original dashed
style. This is a strict style difference on the existing colored line,
not a new UI surface — no legend, no per-segment label, no blocking
alert. A small `ProgressView` (subtle, `.ultraThinMaterial` circle,
top-trailing corner of the map) appears only while a currently-visible
day's route is still being calculated, disappearing the moment it
resolves — the map is always interactive and never blocked while this
shows.

### Missing coordinates

Unchanged from v5, and unaffected by this milestone: `OptimizerRouteMapData`
still excludes any stop without `lat`/`lng` before the calculator ever
sees it (see "Map Visualization → Missing coordinates" above), so a day
handed to `OptimizerRouteCalculator.load` only ever contains stops that
already have usable coordinates. A day with a coordinate gap (e.g. stop 2
of 3 excluded) still produces exactly one request — the surviving stops'
consecutive pair — never inventing a coordinate or skipping straight past
a routable gap (see
`test_load_nonContiguousOrderIndex_stillRequestsConsecutivePairsOverSurvivingStops`).
The missing-coordinate notice text below the map is unmodified.

### Interaction, camera fitting, and performance

All of v5's guarantees hold unchanged: pan/zoom, stop-tap-to-identify via
the native MapKit callout, the callout's explicit-tap-only "open in Apple
Maps" button, and the min-span bounding-region camera fit (Req 8) are
untouched — `OptimizerRouteMap`'s annotation and camera-fitting code
wasn't touched by this milestone, only its overlay-drawing loop. The
camera still only re-fits on first appearance or an actual day-selection
change, same `Coordinator.lastSelectedDayIndex` gate as before — route
segments finishing calculation asynchronously do **not** trigger a camera
re-fit or fight a user's own pan/zoom (Req 8's "do not automatically
fight user camera movement" — the segments update in place, the camera
doesn't move).

Request-count discipline (Req 6): a day's requests only fire once per
screen visit (cache), a repeated `load` call for the same in-flight
day+key is a no-op (doesn't restart or duplicate), and `.task(id:)`
re-firing on day switches only ever calls `load` for the *currently
visible* day(s) — switching rapidly between days N times issues at most N
distinct requests-per-day-worth of legs, never more, regardless of how
many times the underlying SwiftUI view re-renders in between.

### Known limitations

- ~~**Cache is per-screen-instance, not persisted.**~~ **Resolved in
  v11** ("Persistent Optimizer Route Cache" below) — a second, longer-lived
  cache layer now survives reopening the same itinerary.
- ~~**Transport type is fixed to `.automobile`. No walking/transit toggle
  exists.**~~ **Resolved in v12/v18** — v12 added a driving/walking
  toggle; v18 ("Transit Transport Mode") added transit as a third mode
  through the same, already-generic architecture.
- **No manual retry for a failed leg.** A leg that fails once stays a
  straight-line fallback for the rest of that screen visit (it's cached
  as such for the *screen-scoped* day-level cache) — there's no "tap to
  retry this segment" affordance. As of v11, though, leaving and
  reopening the itinerary now *does* retry only that failed leg specifically
  (it was never written to the persistent per-leg cache — see "Persistent
  Optimizer Route Cache → Failure and invalidation behavior" below) rather
  than recomputing the whole day; a per-segment retry button within the
  same visit still wasn't judged worth the added UI surface.
- **No rate-limiting/backoff logic.** Apple doesn't publish a documented
  per-app `MKDirections` quota; this implementation issues requests as
  legs need them (capped naturally by cache + in-flight de-duplication)
  and does not add its own throttling on top. If real-world usage ever
  surfaces MapKit-side throttling, the fix would live entirely inside
  `MKDirectionsRoutingProvider`/`OptimizerRouteCalculator` — the seam this
  milestone built makes that a localized, backward-compatible change.
- **Simulator/offline behavior**: `MKDirections` requires network
  connectivity. In an offline Simulator or a genuinely offline device,
  every leg fails and every day's route silently (well — visibly, via the
  dashed styling) degrades to v5's straight-line rendering. This is
  exactly the documented fallback behavior working as designed, not a
  separate offline-handling code path.

## Bidirectional Itinerary ↔ Map Interaction

Through v6, the route map (`OptimizerRouteMapSection`) and the itinerary
day/stop list (`ItineraryDaySection`, rendered directly by
`TripOptimizerView`) worked **independently** — the map had its own local
`selectedDayIndex` `@State`, and the itinerary list had no selection
concept at all. This milestone connects them: tapping a stop in either
place selects it in both, with the map centering/highlighting the marker
and the itinerary list scrolling to and highlighting the row. It is a
pure interaction/UX change — no optimizer, backend, or BFF code was
touched, and nothing here can trigger a new optimization, a route
recalculation beyond what a genuine day switch requires, or an Apply.

### Architecture/design decision: one shared selection, not two

A new value type, `OptimizerSelection` (`Features/Trips/Components/OptimizerSelection.swift`),
is the **single source of truth** for both "which day is active" and
"which stop is focused":

```swift
struct OptimizerSelection: Equatable {
    var dayIndex: Int?     // nil = "Tümü" (all days) — unchanged v5/v6 semantics
    var stopID:   String?  // the focused/highlighted stop, if any
}
```

`TripOptimizerView` owns it as `@State private var selection = OptimizerSelection()`
and passes it down two ways — never up, never independently re-derived:

- **`OptimizerRouteMapSection(itinerary:selection:onStopSelectedFromMap:)`**
  takes `@Binding var selection: OptimizerSelection`. It **used to** own
  `selectedDayIndex` as its own local `@State`; that's gone. The day-chip
  row now writes through the binding instead of a local property — a
  small, behavior-preserving change (day switching still works exactly as
  in v5/v6), not a rewrite.
- **`ItineraryDaySection(day:selectedStopID:onSelectStop:)`** takes a
  plain (non-binding) `selectedStopID: String?` for reading — it never
  needed to *write* the day, only report taps — plus a
  `onSelectStop: (ItineraryStop) -> Void` closure. This is deliberately
  **not** a `Binding<OptimizerSelection>`: `ItineraryDaySection` has no
  reason to construct a full `OptimizerSelection` value itself (it would
  need `stop.dayIndex` anyway, which `TripOptimizerView` already has
  through the tapped `ItineraryStop`), so keeping it to a read-only value
  + a report-upward closure is the smaller, clearer surface (Req 10's own
  "do not make the production architecture unnecessarily complex just for
  tests" cuts the same way — the simpler shape here also happens to be
  the more testable one, see "Tests" below).

Neither component ever invents its own competing notion of "what's
selected" (Req 13) — `OptimizerRouteMap` (the actual `MKMapView` wrapper)
doesn't even get an `OptimizerSelection` value; it receives the two
already-unpacked primitives it needs (`selectedDayIndex: Int?`,
`selectedStopID: String?`) plus an `onSelectStop` closure, keeping it, as
before, a pure rendering layer with no state of its own beyond its
`Coordinator`'s last-seen bookkeeping.

### The one rule that satisfies both Req 1 and Req 4

`OptimizerSelection.focusing(dayIndex:stopID:)` is the single function
both directions call:

```swift
static func focusing(dayIndex: Int, stopID: String) -> OptimizerSelection {
    OptimizerSelection(dayIndex: dayIndex, stopID: stopID)
}
```

The new selection's `dayIndex` is **always** the tapped stop's own day —
not "whatever was selected before," not "nil/Tümü." This single rule
reads as two different requirements depending on whether the day changes:

- **Req 1 "preserve the current selected day"**: if the tapped stop
  already belongs to the currently-active day, `dayIndex` comes out
  identical to what it was — nothing about the day selection visibly
  changes.
- **Req 4 "switch to that day" when the stop belongs to another day**: if
  the tapped stop belongs to a *different* day (including from "Tümü"),
  `dayIndex` changes to that stop's day — the map narrows to a single-day
  view showing only that day's stops/route, satisfying Req 4's "do not
  draw or display another day's route as the active route" directly (the
  filtering mechanism is the same `OptimizerRouteMapData.visibleDays(selectedDayIndex:)`
  v5/v6 already used).

This is directly why **selecting a stop does not trigger an unnecessary
route recalculation** (Req 1/5/6): `OptimizerRouteMapSection`'s route
loading is gated by `.task(id: selection.dayIndex)` — **not**
`.task(id: selection)`. Swift's `.task(id:)` only re-executes when the id
*value* changes; selecting another stop in the same day leaves `dayIndex`
byte-identical, so the task never re-fires and `OptimizerRouteCalculator.load`
is never even called for that interaction. Only a genuine day change (Req
4's own case) re-triggers it — and even then, `OptimizerRouteCalculator`'s
existing v6 caching means a day already visited (e.g. because "Tümü" had
already loaded every day up front) resolves instantly from cache, not a
fresh network round-trip.

Manually tapping a day chip (not a stop) explicitly **clears** `stopID`
(`OptimizerRouteMapSection`'s day chip action sets
`OptimizerSelection(dayIndex: newValue, stopID: nil)`) — a deliberate
choice: picking a day directly is a "browse this day generally" action,
not a "keep focusing this one stop" action, so the two shouldn't be
conflated.

### Map → Itinerary and Itinerary → Map: symmetric, explicit, one-shot

Each direction is a single explicit action in the tap handler — not an
`onChange`-based reaction inferred from a state diff — because inferring
"who caused this change" from a diff alone is exactly what risks the
camera-update loop Req 7 warns about (see below):

- **Itinerary → Map** (Req 1): `ItineraryDaySection`'s row `Button` calls
  `onSelectStop(stop)`. `TripOptimizerView`'s closure does two things in
  one place: `selection = .focusing(dayIndex: stop.dayIndex, stopID: stop.id)`,
  then `withAnimation { proxy.scrollTo(Self.mapAnchor, anchor: .top) }` —
  the exact same `ScrollViewReader`/`mapAnchor`/`proxy.scrollTo` recipe
  `TripDetailView` already uses for its own `LocationCard` tap (Req 2
  "use the existing SwiftUI scrolling/focus patterns where appropriate" —
  reused verbatim, not reinvented). `OptimizerRouteMap` then sees
  `selectedStopID` change and centers/selects that marker (see "Camera
  behavior" below).
- **Map → Itinerary** (Req 2): `OptimizerRouteMap.Coordinator.mapView(_:didSelect:)`
  (a new delegate method this milestone) resolves the tapped
  `MKAnnotation` back to an `OptimizerMapStop` and calls `onSelectStop`.
  `OptimizerRouteMapSection` updates the shared `selection` through its
  binding, then calls `onStopSelectedFromMap`, which `TripOptimizerView`
  wires to `withAnimation { proxy.scrollTo(ItineraryDaySection.rowID(for: stop.id), anchor: .center) }`
  — the itinerary list scrolls to and centers the corresponding row.
  `ItineraryDaySection` renders every stop row with `.id(Self.rowID(for: stop.id))`
  specifically so this target always exists, for every stop, coordinates
  or not (see "Missing-coordinate behavior" below).

### Avoiding a camera-update loop (Req 7)

Calling `MKMapView.selectAnnotation(_:animated:)` **programmatically**
(the Itinerary → Map direction, inside `OptimizerRouteMap.updateUIView`)
itself fires `MKMapViewDelegate.mapView(_:didSelect:)` — the same
delegate method that reports a *genuine* user tap. Without a guard, that
would create exactly the loop Req 7 warns about: Itinerary tap → `selection`
updates → map focuses + calls `selectAnnotation` → `didSelect` fires →
`onSelectStop` fires → `selection` gets rewritten (to an equal value, but
still a real state write and a real round-trip).

`OptimizerRouteMap.Coordinator.isProgrammaticSelection` breaks this: set
to `true` immediately before the view's own `selectAnnotation` call, and
consumed (reset to `false`) the moment `didSelect` next fires — so exactly
one, and only one, "our own" selection is swallowed, and every other
`didSelect` (i.e. every real user tap) reaches `onSelectStop` normally.
This is the standard, well-known pattern for this exact class of MapKit
problem, not a bespoke invention.

### Camera behavior (Req 7, Req 8)

`OptimizerRouteMap.updateUIView` now distinguishes two independent
questions on every render — "did the focused *stop* change?" and "did the
selected *day* change?" — computed once by comparing against the
`Coordinator`'s last-seen values (which are updated unconditionally right
away, so they never drift stale):

```swift
let dayChanged  = coordinator.lastSelectedDayIndex != selectedDayIndex
let stopChanged = selectedStopID != coordinator.lastFocusedStopID
coordinator.lastSelectedDayIndex = selectedDayIndex
coordinator.lastFocusedStopID    = selectedStopID
```

- If **the stop changed** and it resolves to a real annotation
  (`data.stop(withID:)`-equivalent lookup against the day's annotations):
  center on **just that stop**, small span (`0.01°`, same tight zoom
  `TripMapView.focusedPin` already uses) — **not** the whole day's
  bounding region, even if the day also changed as part of this same
  selection (Req 4's "focus the selected stop," not "fit the whole day").
- **Otherwise** (no stop focus, or focusing a stop with no coordinate —
  see below): fall back to the existing v5/v6 whole-visible-days bounding
  fit, but **only** on first appearance or when the day genuinely changed
  — never on an unrelated re-render, and never overriding a user's own
  pan/zoom mid-browse.

Both branches only run `map.setRegion` when one of these two things
actually changed — an unrelated SwiftUI re-render (e.g. the route-loading
indicator toggling) touches neither `dayChanged` nor `stopChanged` and
therefore never moves the camera, satisfying Req 7's "do not
unnecessarily zoom to the entire route" / "preserve normal map
interaction afterward."

### Marker behavior (Req 8)

No new annotation abstraction — `map.selectAnnotation(match, animated:
true)` (native MapKit) is reused exactly as `TripMapView` already uses it
for its own `focusedPin`. Selecting an annotation natively shows its
callout and applies MapKit's own selected-marker visual state; this
milestone doesn't add a custom highlight ring or alternate marker glyph
on top, matching Req 8's "reuse the existing annotation architecture...
do not introduce a completely new map abstraction unless the current one
cannot support selection cleanly" — the current one supports it cleanly,
so nothing new was introduced.

The itinerary side gets its own, purpose-built highlight (native
selection doesn't extend to SwiftUI list rows): `ItineraryStopRow` gained
an `isSelected: Bool` that swaps its background to
`AppColors.accent.opacity(0.12)` and its border to a 2pt `AppColors.accent`
stroke (vs. the default `AppColors.surface`/1pt `AppColors.border`) —
same accent color already used for the day chips' own selected state, no
new design token introduced.

### Stable identity (Req 3)

`OptimizerSelection.stopID` and `ItineraryDaySection`'s row-highlight
comparison both key off `ItineraryStop.id` — the same stable string
(`"<dayIndex>-<orderIndex>-<placeId-or-\"deleted\">"`) already established
in `OptimizerModels.swift` since the very first optimizer milestone, and
already reused as `OptimizerMapStop.id` by `OptimizerRouteMapData` since
v5. **Nothing here identifies a stop by its position in an array** —
`ForEach(day.stops)` iterates in whatever order the server returned, and
selection survives regardless of that order, regardless of which day is
currently filtered into view (`OptimizerRouteMapData.stop(withID:)`, new
this milestone, searches *all* days, not just the visible ones — see
below), and regardless of whether the itinerary came from a fresh
`.generate` or a `.viewSaved` load (both produce the same `Itinerary`
shape, and `OptimizerSelection`/`stop(withID:)` don't know or care which
path produced it).

### Day-switching behavior (Req 4)

Selecting a stop in a day other than the currently-active one is not a
separate code path — it's the same `.focusing(dayIndex:stopID:)` call
described above, just with a `dayIndex` that happens to differ from the
current selection. The effects cascade naturally through existing
machinery: `selection.dayIndex` changes → `OptimizerRouteMapSection`'s
`.task(id: selection.dayIndex)` re-fires → `loadVisibleDayRoutes()` now
sees only that one day (via `mapData.visibleDays(selectedDayIndex:)`,
unchanged since v5) → `OptimizerRouteMap` draws only that day's
stops/route (never a route connecting across the boundary, same v5/v6
guarantee) → the camera-behavior branch above focuses the specific
selected stop, not the day's whole bounding region.

### Missing-coordinate behavior (Req 9)

A stop without a usable `lat`/`lng` was already excluded from
`OptimizerRouteMapData` entirely since v5 — this milestone changes
nothing about that exclusion, but does change what happens when such a
stop is *selected*:

- **It remains selectable in the itinerary.** `ItineraryStopRow` is now a
  full-row `Button` for *every* stop, unconditionally — v5/v6 never made
  itinerary rows tappable at all, so this is new, and it applies
  identically whether or not the stop has coordinates (`ItineraryStop.id`,
  the identity `isSelected` compares against, never depends on
  `lat`/`lng` — see `test_itineraryStopID_isStableAndComparable_evenWithoutCoordinates`).
- **Selecting it never crashes.** `OptimizerRouteMapData.stop(withID:)`
  (new this milestone) simply can't find the stop — it was never added to
  `allStops` in the first place — and returns `nil`. `OptimizerRouteMap`'s
  focus branch requires `let match = ...` to succeed; when it doesn't, the
  `if` fails and control falls through to the safe day-fit `else` branch
  (or, if the day also didn't change, does nothing at all) — no force
  unwrap, no invalid-coordinate `CLLocationCoordinate2D`, ever constructed
  from a missing-coordinate stop.
- **The map never centers on an invalid coordinate** — by construction,
  not by a defensive check: there is no coordinate to center on in the
  first place, because the stop was never turned into an
  `OptimizerMapStop`/annotation to begin with.
- **The selected itinerary row is still highlighted.** Row selection
  (`stop.id == selectedStopID`) is evaluated entirely independently of
  `OptimizerRouteMapData`/the map — a coordinate-less stop's row turns
  accent-tinted exactly the same way a coordinate-having one's does.

### Generate mode / saved itinerary mode (Req 5, Req 6)

Both modes funnel through the same `TripOptimizerView.resultContent(itinerary:)`
— unchanged by this milestone except for the `ScrollViewReader` wrapper
and the new `selection` wiring, which apply identically regardless of
`mode`. Neither `optimize`/`loadItinerary`/`applyToTrip` on
`TripOptimizerViewModel` was touched, and — more importantly — **none of
them has any relationship to `OptimizerSelection` at all**: there is no
call site anywhere that reads `selection` and decides to call one of
those methods. Selecting/focusing a stop is structurally incapable of
triggering a new optimization request, mutating the saved itinerary or
`TripStop`, or triggering Apply — not because of a guard that prevents it,
but because no code path connects them.

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

`durationDays` (v4 — see "Optimizer Configuration") is the one field
`TripOptimizerConfigView` sends *conditionally*: `Endpoint.body` adds
`duration_days` to the JSON payload only when non-nil, so "Otomatik"
still means *field omitted entirely*, not `"duration_days": null`.
`preferred_start_time`/`preferred_end_time` (v8 — see "Preferred
Start/End Time Controls") are, by contrast, **always** included —
they have no "Otomatik" tri-state, so there is no field-omission
signal for them to carry. `start_date`/`strategy` remain intentionally
omitted — core-api's own `OptimizeTripRequest` defaults still apply
(`greedy_distance`, no fixed start date).

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
- **`TripStopSelectionRow`** (v4) — a `TripStop`-flavored sibling of
  `LibraryRowView`'s own selection-mode row: identical
  `checkmark.circle.fill`/`circle` indicator pair, identical
  card/border/corner-radius recipe, so a user who's already used Trip
  Builder's own multi-select (Library → "Gezi Oluştur") sees the exact
  same visual language here. Shows the stop's name, category chip, and
  city — reuses fields `TripStop` already carries, no new API field
  needed for "enough context to distinguish places."
- **`OptimizerRouteMapData`** (v5; gained `stop(withID:)` in v7; `OptimizerMapDay`
  gained `date`/`chipLabel`/`chipAccessibilityLabel` in v10) — pure
  `Itinerary` → per-day, coordinate-only presentation struct. No
  MapKit/SwiftUI dependency; see "Map Visualization" above.
  `stop(withID:)` is the stable-identity lookup (Req 3) the map's
  focus/select logic and the tests both use; `chipLabel` is the day
  selector's date-aware display text (see "Date-aware Map Day Selector").
- **`OptimizerRouteMap`** (v5; gained `selectedStopID`/`onSelectStop` +
  a `didSelect` delegate method in v7) — the `MKMapView`/`UIViewRepresentable`
  itself, structurally a day-aware sibling of `TripMapView`.
- **`OptimizerRouteMapSection`** (v5; gained `OptimizerRouteCalculator`
  ownership + route-loading lifecycle in v6; gained `OptimizerSelection`
  binding ownership in v7, replacing its own local `selectedDayIndex`
  state; day chips gained date-aware labels + accessibility labels in
  v10) — the SwiftUI wrapper `TripOptimizerView` actually embeds:
  day-selector chips + the map + the missing-coordinate notice + (v6) a
  subtle route-loading indicator, all itinerary-visualization-specific UI
  in one place.
- **`OptimizerRouteCalculator`** / **`OptimizerRoutingProviding`** /
  **`MKDirectionsRoutingProvider`** (v6, all in
  `OptimizerRouteCalculator.swift`) — the real-road-route orchestration
  layer. Not a UI component itself, but lives alongside these three in
  `Features/Trips/Components/` since it exists purely to serve them. See
  "Real Road Route Visualization" above.
- **`OptimizerSelection`** (new, v7, `OptimizerSelection.swift`) — the
  single shared day+stop selection state described in "Bidirectional
  Itinerary ↔ Map Interaction" above. Not a view itself; a pure value type
  plus one pure static helper (`focusing(dayIndex:stopID:)`).
- **`ItineraryDaySection`** (v1; gained `selectedStopID`/`onSelectStop` +
  made every row an interactive, highlightable `Button` in v7; gained
  real-calendar-date headers via `formattedDate` in v9) — previously pure
  display, now also reports taps upward, reflects the shared selection,
  and shows "12 Ağustos 2026" instead of "1. Gün" whenever the itinerary
  has a planning date.
- **`ClockTime`** (v8, `Core/Models/ClockTime.swift`) — the type-safe
  hour/minute value type described in "Preferred Start/End Time Controls"
  above. Not a view; carries the preferred-time state through
  `TripOptimizerConfigViewModel`/`TripOptimizerViewModel`/`Endpoint`,
  converting to `"HH:MM"` only at the network boundary.
- **`PlanningDate`** (v9, `Core/Models/PlanningDate.swift`) — the
  analogous type-safe `(year, month, day)` value type for the optional
  planning date, described in "Trip Planning Date" above. Same design
  language as `ClockTime`: no `Date`/timezone crossing the API boundary,
  `apiValue` converts to `"YYYY-MM-DD"` only at `Endpoint.body`. Scoped to
  the *outgoing* (request-construction) side only — v10's map day-selector
  chips display an already-*incoming* date and deliberately don't route
  through this type; see "Date-aware Map Day Selector → Formatting" above
  for why.

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

315 tests, nineteen files:

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
- **`TripOptimizerViewModelTests.swift`** (32 tests: 29 through v8, plus 3
  new this milestone (v9): `test_optimize_omitsStartDate_whenNotProvided`,
  `test_optimize_forwardsStartDate_whenProvided`, and
  `test_optimize_startDate_doesNotAffectOtherParameters` (a provided
  `startDate` leaves `placeIDs`/`durationDays`/`preferredStartTime`/
  `preferredEndTime` exactly as passed — proving the new parameter is
  additive, not entangled with any existing one). The original 10
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
  `test_optimize_forwardsDurationDays_whenProvided` (v4), confirming
  `optimize(... durationDays: 4 ...)` reaches `.optimizeTrip` with that
  exact value — plus **3 new this milestone (v8)**:
  `test_optimize_forwardsPreferredStartAndEndTime_whenProvided` (a custom
  start/end pair reaches `.optimizeTrip` unchanged),
  `test_optimize_changingOnlyStartTime_doesNotModifyEndTime`, and
  `test_optimize_changingOnlyEndTime_doesNotModifyStartTime` (each
  confirms the *other* time param falls back to `ClockTime.defaultStart`/
  `defaultEnd` when the caller only specifies one — the forwarding-level
  proof of the spec's own "changing only X doesn't modify Y" requirement).
  The two pre-existing forwarding tests
  (`test_optimize_forwardsTripIDAndPlaceIDs_andBearerToken`,
  `test_optimize_forwardsDurationDays_whenProvided`) were updated to also
  assert the default `ClockTime` values now present in every
  `.optimizeTrip` payload.
- **`ItineraryHistoryViewModelTests.swift`** (20 tests: 10 through v14,
  plus 10 new this milestone (v19, Delete Saved Itinerary)) — initial
  state; `load()` happy path with an assertion on the exact endpoint
  called (`.itineraries(tripID:)`); **newest-first ordering**, both as a
  pure unit test directly against `sortedNewestFirst` (no networking at
  all) and as an integration test feeding `load()` a deliberately
  out-of-order server response to confirm the screen doesn't just trust
  it; **empty history** (empty array in, empty array out, no error);
  **API failure** (network error and a `TRIP_NOT_FOUND` server error,
  both asserted against `vm.error`); 401 handling; no-token guard;
  re-entrancy guard (same `AsyncGate` pattern as the optimizer VM).
  **10 new this milestone (v19)**: successful deletion removes the
  correct row (asserted against the exact `.deleteItinerary(itineraryID:)`
  endpoint called); remaining rows keep their order; a failed deletion
  leaves the row intact with `deleteError` set; double submission (via
  `AsyncGate`, a second call while the first is still in flight) is
  ignored and makes no second network request; deleting one itinerary
  never alters the others; deleting the last remaining item empties the
  array; a failed delete can be retried and succeeds; 401 handling; no-token
  guard; and a two-`ItineraryHistoryViewModel` trip-isolation test.
- **`ItineraryApplyHistoryViewModelTests.swift`** (16 tests, new this
  milestone (v20, Apply History & Undo)) — `ItineraryHistoryViewModelTests.swift`'s
  own skeleton, applied to the new screen: initial state; `load()`
  decoding/endpoint-forwarding (`.applyHistory(tripID:)`); server order
  preserved as given (no client-side re-sort — unlike itinerary history,
  `isUndoable` is a per-entry server field, not position-derived, so a
  defensive re-sort wasn't needed here); only the server-flagged entry is
  undoable; a deleted-itinerary entry decodes with `itineraryId: nil`;
  empty history; network/401/no-token guards for `load()`; `load()`
  re-entrancy; `undo()` success (endpoint-forwarding asserted against
  `.undoApplyHistory(tripID:historyID:)`, `undoingID` clears, no error);
  `undo()` failure sets `undoError`; `undo()` double-submission prevented
  (`AsyncGate`, mirroring `deleteItinerary`'s own pattern); `undo()`
  401/no-token guards; and a two-ViewModel trip-isolation test.
- **`OptimizerEndpointTests.swift`** (20 tests: 14 through v8, 5 from v9,
  plus 1 new this milestone (v14):
  `test_optimizeTrip_bodySerializesOvernightRangeAsPlainHHMMStrings` —
  an overnight `ClockTime` pair (`18:00`/`01:00`) serializes to two plain,
  independent `"HH:MM"` strings, exactly like any same-day pair; no
  special overnight encoding was introduced, matching "Overnight Time
  Ranges → Request wire format: unchanged" above) — networking tests,
  pure and synchronous:
  `Endpoint.urlRequest` path/method/body/`Authorization` header, plus
  JSON-decoding tests against realistic server payloads. `duration_days`
  is omitted from the body when `nil` (the default — byte-identical to
  every pre-v4 request), and included with the exact value when provided
  (v4). 3 tests from v8 cover `preferred_start_time`/`preferred_end_time`
  encoding. **5 new this milestone (v9)**:
  `test_optimizeTrip_bodyOmitsStartDate_whenNil` (Req 4 backward
  compatibility — the exact `duration_days` "Otomatik" pattern, reused for
  `start_date`), `test_optimizeTrip_bodyIncludesStartDate_whenProvided`,
  `test_optimizeTrip_bodyZeroPadsStartDate` (single-digit month/day encode
  as `"2026-01-05"`, not `"2026-1-5"` — core-api's `date.fromisoformat`
  requires the padded form), and two decode tests:
  `test_decodesItinerary_withPerDayDate_whenStartDateWasProvided` (a
  two-day fixture with `"date": "2026-09-01"`/`"2026-09-02"` decodes
  correctly and `formattedDate` produces `"1 Eylül 2026"`/`"2 Eylül 2026"`
  — direct evidence of Req 13's "multi-day date derivation," from the
  display-consumption side, since the arithmetic itself is backend-only)
  and `test_decodesItinerary_withoutDateField_decodesNilGracefully`
  (backward compatibility for pre-v9 response shapes, `ItineraryDay`
  constructed directly from a `date`-less JSON object). The two v4
  body-shape tests (`test_optimizeTrip_bodyContainsSelectedPlaceIDs`,
  `test_optimizeTrip_bodyIncludesDurationDays_whenProvided`) had their
  `json.count`/field assertions updated in v8 to reflect that
  `preferred_start_time`/`preferred_end_time` are now always present
  (`1`→`3`, `2`→`4`) — see "Preferred Start/End Time Controls → Request
  wire format" for why; `start_date`'s own conditional-omission pattern
  (v9) didn't require touching those counts again, since it's never
  present unless a test explicitly opts in.
- **`TripOptimizerConfigViewModelTests.swift`** (72 tests: 28 through v8,
  5 from v9, 3 from v14, 15 from v15, 1 from v16, 10 from v17, plus 10
  new this milestone (v18) — see below —):
  default `preferredStartDate` is `nil`
  (unlike `preferredStartTime`/`preferredEndTime`, `start_date` has no
  backend default to mirror — Req 3/11); `setPreferredStartDate` sets the
  date; passing `nil` clears it back to "Otomatik"; setting a date leaves
  place selection/duration/times completely untouched (Req 11 "one
  authoritative configuration model" — a field this independent still
  can't leak into any other); and `canOptimize` is **unaffected** by
  `preferredStartDate` in either state (set or `nil`) — a planning date is
  never a blocking condition, unlike an invalid time range. The original
  17 from v4, no `FakeAPIClient`
  involved at all (this ViewModel makes no network calls — see "Optimizer
  Configuration"): default selection is every stop; default duration is
  Otomatik (`nil`); an empty `stops` array produces an empty,
  non-optimizable selection; toggling deselects/reselects correctly;
  `selectAll`/`deselectAll`; selected count reflects partial selections;
  `canOptimize` is `false` only at exactly zero selected (confirmed `true`
  at exactly one); duration increment from Otomatik lands on `1`, stops
  exactly at the `30`-day upper bound even after many extra increments;
  duration decrement from `1` returns to Otomatik, and decrementing while
  already at Otomatik is a no-op (never produces `0` or negative); a
  100-call increment/decrement stress test confirming the value never
  leaves `[1, 30]` or `nil`; and `selectedPlaceIDsInTripOrder` preserving
  the trip's own stop order regardless of selection/toggle order (not
  `Set` iteration order), both for a full selection and a partial one.
  **11 new this milestone (v8)**: default `preferredStartTime`/
  `preferredEndTime` match `ClockTime.defaultStart`/`defaultEnd` exactly
  (`"09:00"`/`"18:00"`); the default range is valid; `setPreferredStartTime`
  changes only the start time, `setPreferredEndTime` changes only the end
  time (each asserted by checking the *other* property is untouched — the
  spec's own "changing only X doesn't modify Y" requirement, tested at its
  most direct level); a sequential-calls test confirming an earlier
  assignment survives a later, different setter call; `isTimeRangeValid`
  true when start < end, false when start == end (core-api rejects equal
  values too, not just start > end), false when start > end (this last
  assertion was **superseded and removed in v14** — `start > end` is no
  longer invalid, see below); and directly proving Req 4's "Optimize must
  not execute while the configuration is invalid" — `canOptimize` is
  `false` when the time range is invalid *even with a non-empty place
  selection* (isolating that the time check, not the place check, is what's
  blocking), and `true` when both conditions hold.
  **3 new this milestone (v14, Overnight Time Ranges)**: the v8-era
  "start after end" test was renamed and its assertion flipped —
  `test_isTimeRangeValid_true_whenStartAfterEnd_overnightRange` now
  asserts `true` for `19:00 → 09:00`, since that pair is a valid overnight
  window under the new contract, not the invalid one it used to be;
  `test_isTimeRangeValid_true_forOvernightRanges` directly checks the
  milestone's own two minimum examples, `18:00 → 01:00` and `23:30 →
  03:00`; and `test_canOptimize_isTrue_whenTimeRangeIsOvernight` confirms
  an overnight range doesn't block the "Optimize Et" button. The
  pre-existing `test_canOptimize_isFalse_whenTimeRangeInvalid_evenWithPlacesSelected`
  test's own input (`20:00 → 08:00`) was *also* an overnight range under
  the new semantics and had to be changed to a genuinely-invalid
  (equal-value) input to keep testing what it always meant to test.
  **15 new this milestone (v15, Persistent Optimizer Configuration)**:
  no saved configuration produces exactly today's pre-existing defaults;
  a fully-valid saved configuration restores every field exactly; the
  milestone's own selection-reconciliation worked example (saved
  `[1,2,3,4]`, current trip `[1,2,4,5]` → restored `[1,2,4]`, new place
  `5` not auto-selected); an out-of-range saved duration clamps into
  `durationRange`; an invalid (equal-value) saved time range falls back
  to the existing defaults; a valid saved *overnight* range restores
  exactly (proving v14's contract and v15's restoration compose
  correctly); saved start date and saved transport mode both restore
  as-is; five save-on-change tests (one per mutator category — selection,
  duration, time, date, transport mode — each proving the store reflects
  the change immediately, not only on "Optimize Et"); and two
  ViewModel-level trip-isolation tests, mirroring
  `OptimizerSelectionStoreTests.swift`'s own A/B/A pattern — two
  `TripOptimizerConfigViewModel` instances sharing one store never see
  each other's configuration, and reopening Trip A (a fresh ViewModel
  instance, simulating "leave the screen, reopen it") after visiting Trip
  B still restores exactly A's own configuration.
  **1 new this milestone (v16, Persistent Optimizer Transport Mode
  Sync)**: `test_mapOnlyTransportModeChange_beforeAnyConfigScreenVisit_doesNotEmptySelectionOnLaterVisit`
  proves that a transport-mode change written via
  `OptimizerConfigurationStore.updateTransportMode` *before* the config
  screen was ever opened for that trip restores the fallback place IDs on
  the eventual first visit, not an empty selection.
  **10 new this milestone (v17, Optimizer Configuration Transport Mode
  Picker)**: default mode is `.automobile`; `setTransportMode(.walking)`/
  `setTransportMode(.automobile)` each update `vm.transportMode` directly
  (the ViewModel-level assertion the picker's binding actually relies on,
  previously only checked indirectly via the store); a value set through
  the ViewModel is readable from `OptimizerConfigurationStore` exactly the
  way `TripOptimizerView` reads it to seed the map; four tests proving a
  transport-mode change leaves selected places/duration/preferred
  start-end time/preferred start date each individually unchanged; and two
  three-visit trip-isolation round trips (Trip A → Yürüyüş, Trip B →
  Araba, reopen Trip A → still Yürüyüş; and the inverse).
  **10 new this milestone (v18, Transit Transport Mode)**: default mode
  remains `.automobile` after Transit's addition; `setTransportMode(.transit)`
  updates the ViewModel directly, persists to the store, and restores
  after ViewModel recreation; store-readability mirrors how the map reads
  it; trip isolation (Trip B unaffected by Trip A's Transit selection);
  and four non-interference tests (places/duration/time/date all
  unchanged by a switch to Transit) — the exact same test shape as v17's
  own suite, applied to the third case.
- **`OptimizerConfigurationStoreTests.swift`** (14 tests: 7 from v15, 6
  from v16, plus 1 new this milestone (v18)) — `OptimizerConfigurationStore`
  tested entirely on its own, independent of `TripOptimizerConfigViewModel`
  (reconciliation logic lives in the ViewModel, not here — this file only
  proves the store faithfully stores/retrieves/isolates): an unknown trip
  ID returns `nil`; store-then-retrieve returns exactly what was given;
  storing again for the same trip overwrites rather than merges; `remove`
  deletes a stored configuration; two different trips never see each
  other's configuration; and an A→B→A round trip proves visiting B never
  corrupts A's entry — the same shape of isolation proof
  `OptimizerSelectionStoreTests.swift`/`OptimizerRouteCalculatorTests.swift`
  already established for their own stores.
  **6 new this milestone (v16)**, all targeting `updateTransportMode`:
  merging into an existing configuration changes only `transportMode` —
  place selection/duration/start-end time/start date all asserted
  unchanged; merging with no existing configuration creates one seeded
  with the caller's `fallbackSelectedPlaceIDs` (not empty); reading back
  after a write reflects the latest mode; three consecutive calls persist
  only the final value; a mode change for trip A never affects an
  already-stored trip B; and an A→B round trip (both created purely via
  `updateTransportMode`) proves the same isolation guarantee holds for
  this new method, not just for `save`.
  **1 new this milestone (v18)**: `test_updateTransportMode_toTransit_worksExactlyLikeOtherModes`
  proves `updateTransportMode` needed no changes to support the third
  case — merging Transit into an existing configuration changes only
  `transportMode`, leaving place selection/duration untouched.
- **`ClockTimeTests.swift`** (11 tests, v8) — pure
  `XCTest` against `ClockTime`, no SwiftUI/networking involved:
  `apiValue` zero-pads single-digit hour/minute (`9,0` → `"09:00"`) and
  leaves double-digit values alone (`18,30` → `"18:30"`), including
  midnight (`"00:00"`); `defaultStart`/`defaultEnd` encode to core-api's
  exact `"09:00"`/`"18:00"`; `Comparable` orders by hour first, then
  minute, treats equal times as neither-less-than-the-other (not
  accidentally always-`true` or always-`false`), and confirms
  `defaultStart < defaultEnd`; and the `Date` bridge round-trips
  hour/minute exactly (`ClockTime(date: original.asDate) == original`),
  including at midnight — the seam that makes `DatePicker` binding
  possible without ever touching `ClockTime`'s own comparison/encoding
  logic.
- **`PlanningDateTests.swift`** (9 tests, new this milestone) — pure
  `XCTest` against `PlanningDate`, the `ClockTime`-shaped counterpart for
  calendar dates: `apiValue` zero-pads single-digit month/day
  (`"2026-09-01"`) and leaves double-digit ones alone; the `Date` bridge
  round-trips year/month/day exactly; adding one calendar day via the
  `Date` bridge (`Calendar.current.date(byAdding:.day, value: 1, to:)`)
  correctly crosses a month boundary (Jan 31 → Feb 1) and a year boundary
  (Dec 31 → Jan 1) — direct evidence that `PlanningDate`'s `Date` bridge
  doesn't distort the same calendar-day arithmetic `_date_for` performs
  server-side (Req 13 "multi-day date derivation," the pure-value-type
  layer); `displayString` produces the exact Turkish format
  (`"12 Ağustos 2026"`, `"1 Ocak 2026"` — confirms January isn't
  mistranslated); and `Equatable` sanity checks.
- **`APIDateTests.swift`** (7 tests: 4 from v9, plus 3 new this milestone)
  — pure `XCTest` against the new `APIDate.parseDateOnly(_:)`/
  `shortDisplayString(from:)` only (`parse(_:)`/`displayString(from:)` are
  pre-existing, already indirectly exercised elsewhere, out of scope to
  re-test here): `parseDateOnly` parses a valid `"YYYY-MM-DD"` string to
  the correct year/month/day; **rejects** a full `T`-separated datetime
  string (proving this parser and `parse(_:)` are genuinely different, not
  overlapping, parsers for two genuinely different core-api field shapes);
  rejects garbage input (`nil`, not a crash); and chained with
  `displayString(from:)` produces the correct Turkish output — confirming
  the two functions compose the way `ItineraryDay.formattedDate` actually
  uses them (v9). **3 new this milestone (v10)**:
  `test_shortDisplayString_omitsYear` (`"12 Ağustos"`, no `"2026"`
  anywhere in the output — the exact requirement the spec's own preferred
  display example implies); `test_shortDisplayString_januaryIsOcak`
  (confirms the month name comes from `Locale`, not a partial/incorrect
  hand-written table — January is the one month whose Turkish name shares
  no root with its English name, making it a good canary for "is this
  actually localized"); and a three-consecutive-dates test mirroring the
  spec's own `"12 Ağustos" / "13 Ağustos" / "14 Ağustos"` example exactly.
- **`OptimizerRouteMapDataTests.swift`** (29 tests: 19 through v7, 9 from
  v10, plus 1 new this milestone (v11) — see below) — pure `XCTest` against
  `OptimizerRouteMapData`, no MapKit/SwiftUI rendering involved (see "Map
  Visualization → why a new component"): one-stop itinerary; multiple
  stops within a single day (order + exact coordinates preserved);
  multiple days (kept structurally separate, `hasMultipleDays` true, a
  day's stops never leak into another day's array); day indices are
  **not renumbered** even when an earlier day has zero plottable stops (a
  would-be "Day 1" that's entirely coordinate-less doesn't cause the
  remaining day to relabel itself "Day 1"); missing coordinates are
  omitted from the map array but counted, with `orderIndex` gaps
  preserved (not recompacted) so map numbering stays consistent with the
  optimizer's real order; every stop missing coordinates producing empty
  `days` with a full `missingCoordinateCount`; a deleted-source-place stop
  (`placeId`/`lat`/`lng` all `nil`) omitted gracefully, no crash; a
  saved-itinerary-shaped value mapping identically to a freshly-generated
  one (direct evidence for "Saved itinerary behavior" above);
  `visibleDays(selectedDayIndex:)` for nil (all days), a specific day, and
  a day index matching nothing (empty, not a crash); and stop ordering
  staying correct and independent per day across a two-day itinerary.
  **From v7 (`stop(withID:)`, Req 3/9/10)**: a stop's `stop(withID:)`
  result carries the exact same `id` as its source `ItineraryStop`
  (stable identity); it's found regardless of which day is currently the
  `visibleDays` filter target (`stop(withID:)` searches all `days`, not
  just the filtered subset — proving the map can resolve a Map→Itinerary
  or Itinerary→Map focus even for a stop outside the currently-selected
  day, which is exactly the Req 4 day-switch scenario); a
  missing-coordinate stop's ID returns `nil` (never found, never
  crashes); an unknown ID returns `nil`; the same lookup works identically
  against a saved-itinerary-shaped value; and a direct assertion that
  `ItineraryStop.id` (what row-highlight equality compares) is stable and
  non-empty even when `lat`/`lng` are both `nil`. **9 new this milestone
  (v10)**: `OptimizerRouteMapData.init` copies `ItineraryDay.date`
  verbatim into the matching `OptimizerMapDay.date` (no transformation);
  `chipLabel` with a date present shows day+month with **no year and no
  raw ISO substring** (`"12 Ağustos"`, explicitly asserted to not contain
  `"2026"` or `"-"` — Req 1's literal "do not show raw ISO strings"); with
  `date == nil`, falls back to `"1. Gün"` (Req 2); a **malformed** date
  string (`"not-a-real-date"`) falls back the same safe way, no crash (Req
  9's own "malformed/invalid date safely falls back"); three consecutive
  days each format independently and correctly (`"12/13/14 Ağustos"`,
  mirroring the spec's own example); the same mechanism produces identical
  output for a saved-itinerary-shaped value (Req 8); `OptimizerMapDay.id`
  still equals `dayIndex`, not anything date-derived (Req 3, the direct
  proof selection identity is untouched); and two `chipAccessibilityLabel`
  tests (with date: `"1. gün, 12 Ağustos"`; without: `"2. gün"`) — Req 7.
  **1 new this milestone (v11)**:
  `test_init_propagatesItineraryID_intoOptimizerMapDay` — `Itinerary.id`
  is copied verbatim into every one of its days' `OptimizerMapDay.itineraryID`,
  the field the persistent route cache's key relies on for itinerary
  isolation (see "Persistent Optimizer Route Cache → Cache identity").
- **`Support/FakeOptimizerRoutingProvider.swift`** (v6, extended v12) —
  `OptimizerRoutingProviding` test double, same family as `FakeAPIClient`:
  records every `(from, to, mode)` call (`mode` added in v12 — see
  "Optimizer Route Transport Mode → MKDirections" above), an injectable
  `resultProvider` closure for success/failure per call (kept intentionally
  mode-agnostic — see that same doc section for why), and an optional
  `AsyncGate` for deterministic in-flight-state tests. Exists specifically
  because `MKRoute` has no public initializer (see "Real Road Route
  Visualization → Was MKDirections sufficient" above) — this fakes the
  *protocol*, never the concrete MapKit type.
- **`OptimizerTransportModeTests.swift`** (12 tests: 7 from v12, plus 5
  new this milestone (v18)) — `OptimizerTransportMode` tested entirely on
  its own, no `OptimizerRouteCalculator` involved: each case's `title`
  (`"Araba"`/`"Yürüyüş"`/`"Toplu Taşıma"`), each case's `accessibilityLabel`;
  each case's `mapKitType` maps to the correspondingly-named
  `MKDirectionsTransportType` (`.automobile`/`.walking`/`.transit` — the
  literal "automobile → .automobile, walking → .walking, transit →
  .transit" proof); `.transit`'s `symbolName` is `"tram.fill"` and its
  `rawValue` is the stable `"transit"`; and `allCases` now contains all
  three, in `.automobile`/`.walking`/`.transit` order.
  `test_allCases_containsExactlyAutomobileAndWalking_noTransit` (v12) was
  **renamed and its assertion flipped** this milestone —
  `test_allCases_containsAutomobileWalkingAndTransit_inThatOrder` — a
  deliberate contract change (the old test asserted transit's absence,
  which this milestone's entire purpose was to end), not a regression.
- **`OptimizerRouteCalculatorTests.swift`** (45 tests: 23 through v11, 13
  from v12, plus 9 new this milestone (v18) — see below) — `OptimizerRouteCalculator`
  against `FakeOptimizerRoutingProvider`,
  no real `MKDirections` call in any test: cache-key stability (identical
  for the same day+stops, differs for a different day index, differs for
  a different stop order — direct evidence for Req 6's "stable cache
  key"); a single-stop day never calls the provider; a multi-stop day
  requests exactly N−1 legs in the correct from/to order (route request
  construction + ordered stops); a two-day itinerary never issues a
  request that crosses the day boundary (day separation); a successful
  leg is marked `isRoaded: true` with the provider's own coordinates; a
  failing leg falls back to a straight two-point line, `isRoaded: false`,
  no crash; a day with one failing leg among several still resolves the
  other legs (partial-failure graceful degradation); a second `load()`
  call for an already-resolved day makes no new requests (caching); a
  `load()` call repeated while the same day+key is still in flight
  doesn't restart or duplicate the request (simulating repeated SwiftUI
  `body` re-evaluation); day switching leaves both days' routes correct
  and independent, proving Day 1's response can't overwrite Day 2's (Req
  5); a day with a coordinate gap (missing-coordinate stop already
  filtered upstream) still requests exactly the right consecutive pair
  over the surviving stops; and `cancelAll()` doesn't crash and leaves the
  calculator able to load fresh afterward. Verified stable across 3
  repeated full-suite `xcodebuild test` runs (async/timing-sensitive
  tests are exactly the kind that can flake under load, so this was
  checked deliberately, not assumed). **9 new this milestone (v11,
  Persistent Optimizer Route Cache — every test in this group constructs
  TWO separate `OptimizerRouteCalculator` instances sharing ONE
  `OptimizerRouteCache`, simulating "leave the screen, reopen the
  itinerary")**: `cacheKey(for:)` differs for two different
  `itineraryID`s even with an otherwise-identical day+stops (Req 4/15);
  a second calculator loading the exact same itinerary+day as a first
  reuses the result with **zero** new provider calls, synchronously, with
  `isLoading` never observed `true` (Req 6/7/16/17 — the central "does the
  second visit skip the network request" proof); a second calculator
  loading a *different* itinerary with an identical day+stop shape does
  **not** reuse the first's result (Req 4 itinerary isolation); a
  different `dayIndex` within the same itinerary likewise doesn't reuse a
  result (day isolation); reordering the same three stops changes which
  leg pairs are requested, so a reordered day re-requests both legs (Req
  5 stale-order protection); moving one stop's coordinates likewise
  invalidates that leg (Req 5 stale-coordinate protection); a failed leg
  is retried (and can succeed) on a second calculator's visit, since it
  was never cached (Req 8); a partial-failure day caches only its
  successful leg — a second visit re-requests only the leg that failed
  the first time, not the one that already succeeded (Req 9); and
  in-flight de-duplication (repeated `load()` calls while a request is
  already in flight don't restart or duplicate it) still holds with an
  explicitly-injected shared cache, proving the new cache parameter
  doesn't interfere with the pre-existing screen-scoped dedup logic (Req
  10). **13 new this milestone (v12, Optimizer Route Transport Mode)**:
  `cacheKey(for:mode:)` differs between `.automobile` and `.walking` for
  an otherwise-identical day+stops, and omitting `mode` entirely produces
  the same key as passing `.automobile` explicitly (Req 12 default);
  `load(day:)` (mode omitted) reaches the provider requesting `.automobile`,
  `load(day:mode: .walking)` reaches it requesting `.walking` (Req 7's
  literal "automobile → .automobile, walking → .walking are actually
  being requested"); switching mode mid-day immediately clears the
  previously-displayed route and shows the fallback+loading state for the
  new mode, observed mid-flight via an `AsyncGate`-held second request
  (Req 5); repeated `load()` calls with an unchanged mode don't restart
  routing (mirrors the day-selection non-restart guarantee, now proven for
  mode); day switching stays isolated regardless of which mode is active;
  partial failure (one leg fails, one succeeds) still degrades correctly
  under `.walking` specifically; `cancelAll()` + reload still works under a
  non-default mode. **Cache correctness (the milestone's stated critical
  section)**: a single flowing test drives → repeats driving (cache hit) →
  switches to walking (new request) → repeats walking (cache hit) →
  switches back to driving (the *original* driving result served from
  cache, zero new requests — proving the driving entry was never evicted
  or overwritten by walking); a second test proves both modes coexist in
  one shared cache by resolving both from a brand-new calculator instance
  with zero provider calls; a third re-runs v11's stop-reorder structural-
  invalidation test under `.walking` to prove structural and transport-mode
  identity compose correctly; a fourth proves a failed leg is still never
  cached and is retried regardless of mode.
  **9 new this milestone (v18, Transit Transport Mode)**: `cacheKey`
  differs between `.transit` and `.automobile`, and between `.transit`
  and `.walking`; `load(day:mode: .transit)` reaches the fake provider
  requesting `.transit`; a cached transit result is reused synchronously
  with zero new requests; a failed transit leg is never cached and is
  retried on a later visit; a partial-failure day (one leg succeeds, one
  fails) degrades correctly under `.transit` specifically; switching
  walking→transit and switching transit→automobile each issue a fresh
  request rather than reusing the previous mode's cached route; and a
  generic three-mode coexistence test, written as a loop over
  `OptimizerTransportMode.allCases` rather than three hardcoded cases, so
  it automatically re-verifies this guarantee if a fourth mode is ever
  added.
- **`OptimizerRouteCacheTests.swift`** (6 tests, v11) — `OptimizerRouteCache` tested entirely on its own, independent
  of `OptimizerRouteCalculator`: an unknown key returns `nil`; a stored
  value is returned exactly as given; storing again under the same key
  overwrites the previous value; storing/retrieving only ever needs
  `CoreLocation`, never `MapKit` — this file doesn't `import MapKit` at
  all, a structural (not just runtime) proof for Req 11's "cache does not
  require MapKit UI objects"; and two LRU-boundedness tests — exceeding a
  small explicit capacity evicts the least-recently-used entry, and
  *reading* an entry protects it from eviction (proving the eviction order
  is genuinely recency-based, not just insertion-order-based).
- **`OptimizerSelectionTests.swift`** (6 tests, v7) — pure
  `XCTest` against `OptimizerSelection.focusing(dayIndex:stopID:)`, no
  SwiftUI/MapKit involved: focusing a stop already in the current day
  leaves `dayIndex` unchanged (direct evidence for Req 1 "preserve the
  current selected day," and — since `OptimizerRouteMapSection`'s route
  loading is gated on `.task(id: selection.dayIndex)` — indirect but real
  evidence that this same interaction can't trigger a route
  recalculation, Req 1/5/6); focusing a stop in a different day switches
  `dayIndex` to it (Req 4); focusing from "Tümü" (nil) narrows to the
  tapped stop's specific day; a simulated multi-tap "day-switching
  chain" (day 0 → day 1 → another stop still in day 1 → back to day 0)
  ends at the correct day at each step; plus two `Equatable` sanity
  checks. This is the pure core of the bidirectional interaction — the
  actual SwiftUI/MapKit wiring around it (button taps, `ScrollViewReader`,
  `MKMapView` delegate callbacks) is UI glue verified by the build +
  manual/simulator smoke check, not unit tests, per Req 10's own "do not
  make the production architecture unnecessarily complex just for tests."
- **`OptimizerSelectionStoreTests.swift`** (16 tests, new this milestone
  (v13)) — `OptimizerSelectionStore` tested entirely on its own,
  independent of `TripOptimizerView`: basic storage (an unknown itinerary
  ID returns `nil`; store-then-retrieve returns exactly what was given;
  storing again for the same itinerary updates rather than duplicates; a
  `nil`/`nil` selection round-trips correctly); itinerary isolation (two
  different itineraries never see each other's stored selection; an A→B→A
  round trip proves visiting B never corrupts A's entry); every
  `resolveSelection(for:)` validation branch — a valid day+stop restores
  exactly; no stored selection returns the pre-existing default; an
  invalid stored day falls back to the itinerary's first day, no stop; a
  deleted stop (an id that never existed) falls back to the stored day if
  that day is still valid; a deleted stop **and** an invalid day falls
  back to the first available day; a stop found under a day that
  disagrees with the stored `dayIndex` restores using the stop's *actual*
  current day (the direct "follow the stop, not the old day" proof, Req
  6); an empty itinerary (`days: []`) always resolves to `nil`/`nil`
  regardless of what was stored; a stored "Tümü" (`dayIndex: nil`) stays
  "Tümü" — and a dedicated "session behavior" test proving the store's
  data outlives any single conceptual "screen visit" by storing on one
  call and resolving again on the same store instance, standing in for a
  second, independent `TripOptimizerView`/ViewModel pairing (Req 14's own
  "two separate instances using the same store" framing).

### Test results

```
iOS (v9, Trip Planning Date):
Test Suite 'All tests' passed
Executed 157 tests, with 0 failures (0 unexpected) in 0.117-0.168s

core-api (v9, Trip Planning Date):
444 passed, 6 warnings in 44.88s

iOS (v10, Date-aware Map Day Selector):
Test Suite 'All tests' passed at 2026-08-10 11:22:26.288.
Executed 169 tests, with 0 failures (0 unexpected) in 0.156 (0.190) seconds

iOS (v11, Persistent Optimizer Route Cache):
Test Suite 'All tests' passed at 2026-08-10 15:34:36.562.
Executed 185 tests, with 0 failures (0 unexpected) in 0.219 (0.272) seconds
```

`xcodegen generate` followed by a genuinely clean
`xcodebuild -project TripClipApp.xcodeproj -scheme TripClipApp \
-destination 'platform=iOS Simulator,name=iPhone 17 Pro' clean test` —
**TEST SUCCEEDED**, all 169 tests green (157 carried over from v9 + 12
new: 9 in `OptimizerRouteMapDataTests.swift`, 3 in `APIDateTests.swift`).
A separate `clean build` was also run to inspect warnings in isolation:
every warning present traces to pre-existing, untouched files (scattered
`??`-on-non-optional warnings across Auth/Home/Library/Trips/Results
view(-model)s, an `onChange(of:perform:)` deprecation in
`ProcessingView.swift`, a `try?`-result-unused warning in
`PersistenceController.swift`, and a few actor-isolation warnings in
`AppDelegate+BackgroundSession.swift`/`HomeView.swift`) — none in
`PlanModels.swift`, `OptimizerRouteMapData.swift`, or
`OptimizerRouteMapSection.swift`, the three files this milestone touched.
**No backend change this milestone** (pure iOS/display work, per Req 12's
scope exclusions) — core-api/mobile-bff/web-bff suites were not rerun,
since nothing under `services/` was touched.

One real bug was caught and fixed during this milestone's own
implementation, not left in — the second occurrence of the same Swift
gotcha v9 hit first (see "A second Swift gotcha, same family as v9's"
above): giving the new `OptimizerMapDay.date` property an inline default
(`let date: String? = nil`) silently excluded it from the struct's
**synthesized memberwise initializer**, not just `Decodable` synthesis as
in v9 — producing a real compile error, `"extra argument 'date' in call"`,
at the `OptimizerRouteMapData.init` call site. Caught immediately by a
full `xcodebuild build` (not a passing-then-silently-wrong result like
v9's — this one simply didn't compile). Fixed identically to v9: reverted
to a plain `let date: String?` property (no inline default) plus a
hand-written `init(dayIndex:date:stops:)` with the default on the
*parameter* instead.

Verified stable across repeated full-suite `xcodebuild test` runs,
including the clean rebuild — no flakes observed this milestone (the v6
`OptimizerRouteCalculatorTests` flake noted in earlier milestones' test
logs is a known, pre-existing, load-dependent sensitivity in that
specific async test family, unrelated to and untouched by this
milestone's changes).

A live Simulator launch-and-crash-free check was performed (install →
launch → screenshot of the initial screen, confirming the app still boots
and renders normally after this milestone's changes). A full interactive
tap-through (generating a real multi-day itinerary with a planning date
against a running backend, opening the route map, and confirming the day
chips read `"12 Ağustos"`/`"13 Ağustos"` instead of `"1. Gün"`/`"2. Gün"`)
was **not** performed in this environment — same limitation as every
prior milestone's testing notes (no XCUITest/accessibility automation
harness here, and reaching this screen requires a live backend +
authenticated session + a real multi-day trip with a planning date) —
that level of verification relies on the 169 passing iOS tests (12 of
them new this milestone, directly exercising `chipLabel`/
`chipAccessibilityLabel` against real and malformed date strings) plus
the clean build instead.

### Test results (v11 — Persistent Optimizer Route Cache)

`xcodegen generate` (to register the two new files,
`OptimizerRouteCache.swift` and `OptimizerRouteCacheTests.swift`) followed
by a genuinely clean `xcodebuild ... clean test` — **TEST SUCCEEDED**, all
185 tests green (169 carried over from v10 + 16 new: 9 in
`OptimizerRouteCalculatorTests.swift`, 6 in the new
`OptimizerRouteCacheTests.swift`, 1 in `OptimizerRouteMapDataTests.swift`).
A separate `clean build` was run to inspect warnings in isolation: every
warning present traces to pre-existing, untouched files (the same
scattered `??`-on-non-optional warnings, the `ProcessingView.swift`
`onChange` deprecation, the `PersistenceController.swift` `try?` warning,
and the `AppDelegate+BackgroundSession.swift`/`HomeView.swift`
actor-isolation warnings already present before this milestone) — none in
`TripClipApp.swift`, `OptimizerRouteCache.swift`,
`OptimizerRouteCalculator.swift`, `OptimizerRouteMapData.swift`,
`OptimizerRouteMapSection.swift`, or `TripOptimizerView.swift`, the six
files this milestone touched or added. **No backend/BFF change this
milestone** (pure iOS caching-layer work, per Req 19's scope exclusions
and Req 20) — core-api/mobile-bff/web-bff suites were not rerun, since
nothing under `services/` was touched.

**Proof the second visit skips the network request** — the central claim
of this milestone — comes directly from
`test_persistentCache_survivesCalculatorRecreation_secondVisitReusesResult_noNewRequest`:
a first `OptimizerRouteCalculator` (backed by `firstVisitProvider`) loads
a day and the test asserts `firstVisitProvider.callCount == 1`; a second,
entirely separate `OptimizerRouteCalculator` instance (backed by a fresh
`secondVisitProvider`, sharing only the `OptimizerRouteCache`) then loads
the exact same day, and the test asserts `secondVisitProvider.callCount
== 0` — a call-count assertion, not a timing measurement, satisfying Req
17's explicit "do not rely only on timing measurements."

No bugs were caught mid-implementation this milestone (unlike v9 and v10,
which each hit a real Swift `Decodable`/memberwise-init gotcha) — the one
subtlety that surfaced during test-writing rather than compilation was
cancellation ordering: an early implementation wrote a leg's result to
the persistent cache *before* re-checking `Task.isCancelled` after the
`await provider.route(...)` call returned, which would have let a
cancelled-but-still-completing task leak a result into the shared cache
and broken `test_cancelAll_doesNotCrash_andAllowsFreshLoadAfterward`'s
"a reload after cancellation makes a genuinely new request" assertion.
Moving the cancellation check to immediately after the `await` (before
appending the segment or calling `cache.store`) fixed it and kept that
pre-existing v6 test passing unmodified — see "Persistent Optimizer Route
Cache → Failure and invalidation behavior" above.

Verified stable across repeated full-suite `xcodebuild test` runs — no
flakes observed (the v6 `OptimizerRouteCalculatorTests` sensitivity noted
in earlier milestones' logs is a known, pre-existing, load-dependent
characteristic of that async test family, unrelated to this milestone).

A live Simulator launch-and-crash-free check was performed (install →
launch → screenshot of the initial screen), confirming the new
`.environment(optimizerRouteCache)` injection in `TripClipApp.swift`
doesn't break app startup. A full interactive tap-through (open a saved
itinerary from Itinerary History, wait for its routes to draw, back out,
reopen the same saved itinerary, and confirm the map draws instantly with
no spinner) was **not** performed in this environment — same limitation
as every prior milestone's testing notes (no XCUITest/accessibility
automation harness here, and reaching this screen requires a live backend
+ authenticated session + a real saved itinerary with coordinates) — that
level of verification relies on the 185 passing iOS tests (16 of them new
this milestone, including the explicit call-count proof above) plus the
clean build instead.

### Test results (v12 — Optimizer Route Transport Mode)

`xcodegen generate` (to register the two new files,
`OptimizerTransportMode.swift` and `OptimizerTransportModeTests.swift`)
followed by a genuinely clean `xcodebuild ... clean test` — **TEST
SUCCEEDED**, all 205 tests green (185 carried over from v11 + 20 new: 13
in `OptimizerRouteCalculatorTests.swift`, 7 in the new
`OptimizerTransportModeTests.swift`). A separate `clean build` was run to
inspect warnings in isolation: every warning present traces to
pre-existing, untouched files (the same set noted in every prior
milestone's Test results) — none in `OptimizerTransportMode.swift`,
`OptimizerRouteCalculator.swift`, `OptimizerRouteMapSection.swift`, or
`Support/FakeOptimizerRoutingProvider.swift`, the files this milestone
touched or added. **No backend/BFF change this milestone** (pure iOS
route-visualization work) — core-api/mobile-bff/web-bff suites were not
rerun, since nothing under `services/` was touched.

A full `xcodebuild build-for-testing` was also run in isolation (before
the full `test` run) specifically to confirm the **zero required test-file
edits** claim implied by Req 12's backward-compatibility requirement: it
produced no errors on the first attempt, meaning every pre-v12 test call
site (`calculator.load(day:)`, `OptimizerRouteCalculator.cacheKey(for:)`,
every `OptimizerMapDay(...)` construction) compiled against the new
defaulted signatures without a single line of pre-existing test code
needing to change — the only test-file edits this milestone made were
additive (new test functions, plus the three-line `Call.mode` addition to
`FakeOptimizerRoutingProvider`, which no existing test constructs
directly).

**Proof mode participates in cache identity correctly** — the milestone's
own stated "CRITICAL" section — comes from
`test_transportModeCache_drivingThenWalkingThenBackToDriving_eachModeIndependentlyCached`:
a single calculator/provider pair drives, repeats driving (`callCount`
unchanged — cache hit), switches to walking (`callCount` increments — new
request), repeats walking (`callCount` unchanged again), then switches
*back* to driving and asserts `callCount` is **still** unchanged from the
walking step — proving the original driving cache entry survived the
walking requests untouched, not merely that "some" cache entry existed.

One real design decision was revisited during implementation, not a bug:
the initial draft considered giving `MKDirectionsRoutingProvider.route`'s
new `mode` parameter a default value at the protocol-requirement level to
minimize the diff further, but Swift protocol requirements cannot carry
default parameter values (only concrete-type extensions can, which would
have meant every conformer redeclaring the default separately, an
inconsistency risk for a two-conformer protocol) — the milestone instead
accepted the smaller, more explicit change of making `mode` required on
the protocol method and defaulting it one layer up, on
`OptimizerRouteCalculator.load(day:mode:)`, which is the only place any
caller (production or test) actually invokes routing indirectly. This is
documented as a deliberate architectural choice, not a workaround.

Verified stable across repeated full-suite `xcodebuild test` runs — no
flakes observed (the same v6 `OptimizerRouteCalculatorTests` async-timing
sensitivity noted in every prior milestone's logs, unrelated to this
milestone's changes).

A live Simulator launch-and-crash-free check was performed (install →
launch → screenshot of the initial screen). A full interactive tap-through
(opening the route map, toggling Araba/Yürüyüş, and confirming the
polyline visibly changes and no stale route lingers) was **not** performed
in this environment — same limitation as every prior milestone's testing
notes (no XCUITest/accessibility automation harness here, and reaching
this screen requires a live backend + authenticated session + a real
multi-stop trip) — that level of verification relies on the 205 passing
iOS tests (20 of them new this milestone, including the explicit
mode-reaches-provider and mode-participates-in-cache-identity proofs
above) plus the clean build instead.

### Test results (v13 — Persistent Optimizer Map Selection)

`xcodegen generate` (to register the two new files,
`OptimizerSelectionStore.swift` and `OptimizerSelectionStoreTests.swift`)
followed by a genuinely clean `xcodebuild ... clean test` — **TEST
SUCCEEDED**, all 221 tests green (205 carried over from v12 + 16 new, all
in the new `OptimizerSelectionStoreTests.swift`). A separate `clean
build` was run to inspect warnings in isolation: every warning present
traces to pre-existing, untouched files (the same set noted in every
prior milestone's Test results) — none in `OptimizerSelectionStore.swift`,
`TripClipApp.swift`, or `TripOptimizerView.swift`, the three files this
milestone touched or added. `OptimizerRouteMapSection.swift`,
`ItineraryDaySection.swift`, `OptimizerRouteMap.swift`, and
`OptimizerRouteCache.swift` were **not** touched at all this milestone —
confirmed by `git diff --stat`, directly verifying Req 2's "do not put
persistence logic inside those views" and Req 15's "do not modify
`OptimizerRouteCache`." **No backend/BFF change this milestone** (pure
iOS UI-state work) — core-api/mobile-bff/web-bff suites were not rerun,
since nothing under `services/` was touched.

Every pre-existing optimizer test file — `OptimizerRouteCalculatorTests.swift`,
`OptimizerRouteCacheTests.swift`, `OptimizerSelectionTests.swift`,
`OptimizerTransportModeTests.swift`, `OptimizerRouteMapDataTests.swift`,
`TripOptimizerViewModelTests.swift` — passed completely unmodified,
directly satisfying the "no regressions in existing optimizer tests /
route map tests / route calculator/cache tests / transport mode tests"
verification checklist: since `OptimizerRouteCalculator`, `OptimizerRouteCache`,
`OptimizerRouteMap`, and `OptimizerTransportMode` were none of them
touched, there was no code path for this milestone to have regressed in
the first place — the passing suite is confirmation, not incidental
overlap.

Verified stable across repeated full-suite `xcodebuild test` runs — no
flakes observed (the same v6 `OptimizerRouteCalculatorTests` async-timing
sensitivity noted in every prior milestone's logs, unrelated to this
milestone, which added no new asynchronous code — `OptimizerSelectionStore`
itself is fully synchronous).

A live Simulator launch-and-crash-free check was performed (install →
launch → screenshot of the initial screen), confirming the new
`.environment(optimizerSelectionStore)` injection in `TripClipApp.swift`
doesn't break app startup. A full interactive tap-through (select Day 2 /
a stop, leave the optimizer, reopen the same itinerary, confirm Day 2 /
that stop is still focused with no route re-fetch) was **not** performed
in this environment — same limitation as every prior milestone's testing
notes (no XCUITest/accessibility automation harness here, and reaching
this screen requires a live backend + authenticated session + a real
multi-day trip) — that level of verification relies on the 221 passing
iOS tests (16 of them new this milestone, covering every validation
branch and the itinerary-isolation/session-behavior guarantees directly)
plus the clean build instead.

### Test results (v14 — Overnight Time Ranges)

`xcodegen generate` followed by a genuinely clean `xcodebuild ... clean
test` — **TEST SUCCEEDED**, all 225 tests green (221 carried over from
v13 + 4 new: 3 in `TripOptimizerConfigViewModelTests.swift`, 1 in
`OptimizerEndpointTests.swift`). A separate `clean build` was run to
inspect warnings in isolation: every warning present traces to
pre-existing, untouched files (the same set noted in every prior
milestone's Test results) — none in `TripOptimizerConfigViewModel.swift`,
the only production file this milestone touched.

**core-api's own suite (the bulk of this milestone) was run in full**
(`pytest tests/ -q` from `services/core-api`): 490 tests passed (441
before this milestone), zero regressions — see `docs/trip-optimizer.md`
"Overnight Time Ranges" and its own "Testing" section update for the
complete backend test breakdown (a new `test_overnight_time_window.py`
testing the shared `PlanningTimeWindow`/`_day_relative_window` helpers
directly, plus overnight-specific additions across
`test_optimization_strategy.py`, `test_ortools_strategy.py`,
`test_strategy_comparison.py`, and `test_trip_optimization.py`). Three
pre-existing tests across the backend suite encoded the *old* "overnight
= invalid/skipped" contract and had to be updated, not just extended —
`test_arrival_after_closing_gets_conflict_warning`-adjacent regression
during implementation (see below), `test_invalid_time_window_falls_back_to_default_window`
(ortools), and `test_end_time_before_start_time_is_rejected` (API-level)
— each is documented in `docs/trip-optimizer.md`'s own testing section
with exactly what changed and why.

One real bug was caught and fixed during implementation, not left in: an
early version of the shared `_resolve_arrival` helper unconditionally
rolled a place's already-closed window forward by a full day whenever
`current_time` was already past it — correct for Case C (an overnight
*planning* day, an early place window like `"00:00-04:00"`) but wrong for
the common, non-overnight case (a place open `"07:00-08:00"` checked
against a default `09:00-18:00` day used to correctly warn "çakışıyor";
the naive version instead silently treated it as "opens tomorrow" and
suppressed the warning entirely). Caught immediately by the *existing*,
unmodified `test_arrival_after_closing_gets_conflict_warning` regression
test failing on the very first full-suite run after the change — not by
a new test, but by an old one doing exactly its job. Fixed by making the
day-rollover conditional on the shifted occurrence still fitting within
`day_end` (see `docs/trip-optimizer.md` "Overnight Time Ranges → New
shared value types and helpers" for the corrected logic) — the same fix
that makes Case D (a window that can *never* fit any occurrence of a
given day) correctly fall through to the existing flush/overflow
mechanism instead of looping.

Verified stable across repeated full-suite runs on both sides — no flakes
observed (backend: deterministic OR-Tools search, per "Determinism"; iOS:
no new asynchronous code, `TripOptimizerConfigViewModel`'s validation is
a pure synchronous property).

A live Simulator launch-and-crash-free check was performed (install →
launch → screenshot of the initial screen). A full interactive
tap-through (entering `18:00`/`01:00` in the "Planlama Saatleri" pickers
and confirming "Optimize Et" stays enabled, then generating a real
overnight-scheduled itinerary against a running backend) was **not**
performed in this environment — same limitation as every prior
milestone's testing notes (no XCUITest/accessibility automation harness
here, and reaching this screen requires a live backend + authenticated
session + a real multi-stop trip) — that level of verification relies on
the 225 passing iOS tests plus the 490 passing core-api tests (49 of them
new/updated this milestone), plus both clean builds, instead.

### Test results (v15 — Persistent Optimizer Configuration)

`xcodegen generate` (to register the two new files,
`OptimizerConfiguration.swift`/`OptimizerConfigurationStore.swift`, and
their test counterparts) followed by a genuinely clean `xcodebuild ...
clean test` — **TEST SUCCEEDED**, all 247 tests green (225 carried over
from v14 + 22 new: 15 in `TripOptimizerConfigViewModelTests.swift`, 7 in
the new `OptimizerConfigurationStoreTests.swift`). A separate `build-for-testing`
run (before adding any new test code) confirmed **zero required edits to
any pre-existing test** — every one of `TripOptimizerConfigViewModelTests.swift`'s
dozens of `TripOptimizerConfigViewModel(stops: ...)` call sites compiled
against the new `tripID`/`configStore`-defaulted initializer signature
unchanged, directly matching the `OptimizerRouteCalculator.init(provider:cache:)`
backward-compatibility precedent from v11. A `clean build` found no new
warnings — none in `OptimizerConfiguration.swift`,
`OptimizerConfigurationStore.swift`, `TripOptimizerConfigViewModel.swift`,
`TripOptimizerConfigView.swift`, `TripDetailView.swift`,
`TripOptimizerView.swift`, `OptimizerRouteMapSection.swift`, or
`TripClipApp.swift`, the eight files this milestone touched or added.

Every pre-existing optimizer test file — `OptimizerRouteCalculatorTests.swift`,
`OptimizerRouteCacheTests.swift`, `OptimizerSelectionStoreTests.swift`,
`OptimizerTransportModeTests.swift`, `OptimizerRouteMapDataTests.swift`,
`TripOptimizerViewModelTests.swift`, `OptimizerEndpointTests.swift` — passed
completely unmodified, directly confirming Req 18's full regression
checklist (route calculation, route cache, route map, selection store,
transport mode, itinerary history, apply-to-trip all untouched): none of
those files' underlying production code was touched by this milestone, so
there was no code path for a regression to hide in.

**No backend/BFF change this milestone** (pure iOS session-state work,
per Req 21's scope exclusions) — core-api/mobile-bff/web-bff suites were
not rerun, since nothing under `services/` was touched.

Verified stable across repeated full-suite runs — no flakes (this
milestone's code is entirely synchronous, same as `TripOptimizerConfigViewModel`
already was).

A live Simulator launch-and-crash-free check was performed (install →
launch → screenshot of the initial screen), confirming the new
`.environment(optimizerConfigurationStore)` injection in `TripClipApp.swift`,
plus the new `@Environment(OptimizerConfigurationStore.self)` reads in
`TripDetailView`/`TripOptimizerView`, don't break app startup. A full
interactive tap-through (open Trip A's optimizer config, change several
settings, leave, reopen Trip A and confirm restoration, then open Trip B
and confirm none of Trip A's settings leaked in) was **not** performed in
this environment — same limitation as every prior milestone's testing
notes (no XCUITest/accessibility automation harness here, and reaching
this screen requires a live backend + authenticated session + at least
two real trips with places) — that level of verification relies on the
247 passing iOS tests (22 of them new this milestone, including the two
dedicated ViewModel-level trip-isolation tests and the exact
selection-reconciliation worked example from the milestone spec) plus the
clean build instead.

### Test results (v16 — Persistent Optimizer Transport Mode Sync)

`xcodegen generate` (no new files this time — every file touched already
existed) followed by a genuinely clean `xcodebuild ... clean test` —
**TEST SUCCEEDED**, all 254 tests green (247 carried over from v15 + 7
new: 6 in `OptimizerConfigurationStoreTests.swift`, 1 in
`TripOptimizerConfigViewModelTests.swift`). Every one of v15's own
restoration/reconciliation/trip-isolation tests passed completely
unmodified, confirming the spec's own "existing restoration tests
continue passing unchanged" requirement.

A separate `clean build` found no new warnings in
`OptimizerRouteMapSection.swift`, `TripOptimizerView.swift`,
`OptimizerConfigurationStore.swift`, `OptimizerConfiguration.swift`, or
`TripOptimizerConfigViewModel.swift` — the five files this milestone
touched or added to. The pre-existing warning list is unchanged from v15
(all in unrelated files — `LoginView.swift`, `HomeView.swift`,
`AppDelegate+BackgroundSession.swift`, etc. — none introduced by this
milestone).

**No backend/BFF change this milestone** (pure iOS session-state work) —
core-api/mobile-bff/web-bff suites were not rerun, since nothing under
`services/` was touched. `OptimizerRouteCache`/`OptimizerRouteCalculator`
were also not modified — the full `OptimizerRouteCacheTests.swift`/
`OptimizerRouteCalculatorTests.swift` suites passed unmodified, confirming
the mode-keyed cache behavior from v12 is untouched.

A live Simulator launch-and-crash-free check was performed (install →
launch → screenshot of the initial screen) — clean, unauthenticated
launch screen, no crash. A full interactive tap-through (change transport
mode on the route map, leave and reopen the same trip's optimizer,
confirm the mode restored; repeat for a second trip and confirm no
leakage) was **not** performed in this environment — same limitation as
every prior milestone (no XCUITest/accessibility automation harness here,
and reaching this screen requires a live backend + authenticated session
+ at least one trip with a generated or saved itinerary). That level of
verification relies on the 254 passing iOS tests (7 of them new this
milestone, including the map-only-change-before-any-config-visit
integration test and the full `updateTransportMode` isolation suite) plus
the clean build instead.

### Test results (v17 — Optimizer Configuration Transport Mode Picker)

`xcodegen generate` (no new files — every file touched already existed)
followed by a genuinely clean `xcodebuild ... clean test` —
**TEST SUCCEEDED**, all 264 tests green (254 carried over from v16 + 10
new, all in `TripOptimizerConfigViewModelTests.swift`). Every v15/v16
restoration, persistence, and trip-isolation test passed completely
unmodified. Repeated across three consecutive clean runs to confirm
stability — an earlier single-run failure was traced to a manually
launched app instance left running on the same Simulator from an
interactive smoke-test step, not to any test in this change; three
subsequent clean runs (and the officially reported run) were all
264/264 green.

A separate `clean build` found no new warnings in
`TripOptimizerConfigView.swift` or `TripOptimizerConfigViewModel.swift` —
the two files this milestone touched. The pre-existing warning list is
byte-for-byte identical to v16's (all in unrelated files).

**No backend/BFF change this milestone.** `OptimizerRouteMapSection.swift`,
`OptimizerConfigurationStore.swift`, `OptimizerConfiguration.swift`,
`OptimizerRouteCache.swift`, and `OptimizerRouteCalculator.swift` were
**not** modified — this milestone is additive UI wired to pre-existing
ViewModel/store methods only, exactly as scoped.

A live Simulator launch-and-crash-free check was performed (install →
launch → screenshot of the initial screen) — clean, unauthenticated
launch screen, no crash. The full interactive loop described in the
milestone spec (config → Yürüyüş → generate → map opens in Yürüyüş → map
→ Araba → reopen config → config shows Araba, and the inverse) was
**not** performed in this environment — same standing limitation as every
prior milestone (no XCUITest/accessibility automation harness, and
reaching this screen requires a live backend + authenticated session +
at least one trip with places). That level of verification relies on the
264 passing iOS tests (10 of them new this milestone, directly covering
ViewModel-level mode changes, non-interference with other fields, and
both trip-isolation directions) plus the clean build instead.

### Test results (v18 — Transit Transport Mode)

`xcodegen generate` (no new files — every file touched already existed)
followed by a genuinely clean `xcodebuild ... clean test` —
**TEST SUCCEEDED**, all 289 tests green (264 carried over from v17 + 25
new: 5 in `OptimizerTransportModeTests.swift`, 9 in
`OptimizerRouteCalculatorTests.swift`, 10 in
`TripOptimizerConfigViewModelTests.swift`, 1 in
`OptimizerConfigurationStoreTests.swift`) — green on the **first** run,
with no bug found and no test needing adjustment beyond the one
deliberate contract change
(`test_allCases_containsExactlyAutomobileAndWalking_noTransit` →
renamed/flipped). This is a direct, positive confirmation of the
milestone's own architecture inspection: because every layer was already
generic over `OptimizerTransportMode`, extending the enum introduced no
new code paths capable of a genuinely new bug.

A separate `clean build` found no new warnings in
`OptimizerTransportMode.swift`, `OptimizerRouteCalculator.swift`, or
`OptimizerRouteMapSection.swift` — the three production files this
milestone touched. The pre-existing warning list is unchanged from v17
(all in unrelated files).

**No backend/BFF change this milestone.** `OptimizerConfiguration.swift`,
`OptimizerConfigurationStore.swift`, and `OptimizerRouteCache.swift` were
**not** modified — confirmed by `git status`/`git diff`, and directly
matching the milestone's own prediction that the existing architecture
would require little-to-no structural change.

A live Simulator launch-and-crash-free check was performed (install →
launch → screenshot of the initial screen) — clean, unauthenticated
launch screen, no crash. Live `MKDirections` transit routing was **not**
exercised — no authenticated backend session or real trip data is
available in this environment to reach the optimizer screens
interactively, and transit coverage/data availability cannot be
meaningfully asserted from a screenshot even if it were reached. Per the
milestone's own instruction, the failure/fallback path was verified
deterministically instead (`test_transitCache_failedRequest_isNeverCached`,
`test_transitPartialFailure_preservesSuccessfulLegs`, both against
`FakeOptimizerRoutingProvider` simulating "no transit route found") — an
honestly-reported environment limitation, not a weakened test.

### Test results (v19 — Delete Saved Itinerary from History)

All four suites green:

- **Core-API**: `pytest` — **503/503 passed** (490 carried over from v18 +
  13 new in `test_trip_optimization.py`). No migration was added or run —
  confirmed unnecessary before writing any code (see "Delete Saved
  Itinerary → Cascading behavior" above).
- **Mobile BFF**: `pytest` — **107/107 passed** (102 carried over + 5 new).
- **Web BFF**: `pytest` — **64/64 passed** (59 carried over + 5 new). Two
  of the five new tests initially failed on first write — a direct 1:1
  copy of Mobile BFF's expectations (`403` for missing auth, `500` for
  upstream `INTERNAL_SERVER_ERROR`) assumed Web BFF's error mapping was
  identical to Mobile BFF's. It isn't:
  `error_wrapper._parse_core_error` remaps `INTERNAL_SERVER_ERROR` to
  `503`, and missing auth returns `401`, not `403` — both **pre-existing**
  Web BFF behaviors, confirmed unrelated to this milestone by inspecting
  `error_wrapper.py` and the file's own existing `test_apply_itinerary_requires_auth`/
  `test_optimize_requires_auth` tests. The two new tests were corrected to
  match the actual, correct, already-shipping behavior rather than the
  mistaken assumption — not a code bug, a caught test-authoring mistake.
- **iOS**: `xcodebuild ... clean test` — **TEST SUCCEEDED, 299/299**
  (289 carried over from v18 + 10 new in `ItineraryHistoryViewModelTests.swift`).

A separate `clean build` found no new warnings in any of the seven
Swift/Python-adjacent files this milestone touched or added
(`Endpoint.swift`, `ItineraryHistoryView.swift`,
`ItineraryHistoryViewModel.swift`, plus the four backend files). One
near-new warning was caught and fixed at the source: the new
`Logger.network.warning(...)` call in `deleteItinerary` initially copied
`load()`'s own `apiError.localizedDescription ?? ""` idiom verbatim,
which produces the same harmless-but-real "non-optional left side of `??`"
warning already present in ~15 other pre-existing call sites throughout
this codebase (confirmed via a `git stash`-based control build that the
identical warning already existed, unmodified, in `errorState`'s
pre-existing `error.localizedDescription ?? "..."` line before this
milestone touched the file). Rather than leave a second instance of an
already-tolerated wart, the redundant `?? ""` was dropped from this one
new line — zero pre-existing code was touched to do it.

A live Simulator launch-and-crash-free check was performed (install →
launch → screenshot of the initial screen) — clean, unauthenticated
launch screen, no crash. The full interactive delete flow (swipe → confirm
→ row disappears; delete the applied itinerary → reopen the trip → no
dangling state; delete while a different itinerary's detail screen was
recently open → reopen History → no broken destination) was **not**
exercised interactively in this environment — same standing limitation as
every prior milestone (no XCUITest/accessibility automation harness, and
reaching these screens requires a live backend + authenticated session +
an actual trip with a saved itinerary). That level of verification relies
on the 299 passing iOS tests plus the 503+107+64 passing backend/BFF
tests (674 total across all four suites) and the clean build instead.

### Test results (v20 — Apply History & Undo)

All four suites green, plus a migration verified both directions:

- **Migration** (`b8e4d2f6a913_add_trip_itinerary_apply_history`):
  `alembic upgrade head` and `alembic downgrade -1` both run cleanly
  against a fresh SQLite DB (full chain from the very first migration).
  No existing migration was modified.
- **Core-API**: `pytest` — **529/529 passed** (503 carried over from v19 +
  26 new in `test_trip_optimization.py`). One of those 26 caught a real,
  pre-existing-but-newly-exposed bug on its very first run — see "A real
  bug found and fixed" above — fixed, then green.
- **Mobile BFF**: `pytest` — **117/117 passed** (107 carried over + 10 new).
- **Web BFF**: `pytest` — **74/74 passed** (64 carried over + 10 new), all
  green on the first write this time (the v19 error-mapping lesson —
  Web BFF's `401`/`503` behaviors differ from Mobile BFF's — was applied
  proactively rather than discovered again).
- **iOS**: `xcodebuild ... clean test` — **315/315** (299 carried over +
  16 new in `ItineraryApplyHistoryViewModelTests.swift`). One single-run
  failure surfaced in `OptimizerRouteCalculatorTests.swift` — a file this
  milestone never touched — confirmed to be a pre-existing async-timing
  flake (same class of flake this file's own testing notes have
  documented before), not a regression, via three consecutive clean
  reruns, all 315/315.

A separate `clean build` found no new warnings in any of the eleven
Swift/Python files this milestone touched or added. One near-new warning
was caught and fixed at the source, the same way v19 handled an identical
situation: `ItineraryApplyHistoryView`'s new `errorState` initially copied
`ItineraryHistoryView`'s own (pre-existing, still-present)
`error.localizedDescription ?? "..."` idiom verbatim — `APIError.localizedDescription`
resolves to a non-optional `String`, making the fallback dead code and
the warning genuinely avoidable; dropped from this one new line only, no
pre-existing file touched.

**No Docker build was performed** — inspected whether it was needed per
the milestone's own conditional instruction ("if migration/runtime
changes require it") and judged it unnecessary: the local venv used for
every test run above shares the exact same `requirements.txt`/dependency
graph the Docker image would build from, `python -c "from app.main import
app"` already succeeds (confirming no import-time errors from the new
model/routes), and the migration was independently verified end-to-end
against a fresh SQLite database outside of pytest's own fixture-managed
DB. A full image build (this project bundles ML dependencies — PyTorch
etc.) would have re-verified the same dependency graph at meaningfully
higher cost for no additional signal.

A live Simulator launch-and-crash-free check was performed (install →
launch → screenshot of the initial screen) — clean, unauthenticated
launch screen, no crash. The full interactive apply/undo flow was **not**
exercised live — see "Simulator / live verification" above; covered by
the 315+529+117+74 = 1035 passing tests across all four suites instead.

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

## Assumptions / limitations (v5 — Map Visualization)

- **Straight-line route segments, not real road geometry** — deliberately,
  per this milestone's own scope; see "Map Visualization → Route rendering
  limitation" above. No routing API was called or is planned to be called
  within this milestone.
- **No live location / "you are here"** — `showsUserLocation` is `false`,
  same as `TripMapView`. This is a preview of the optimizer's *plan*, not
  a live navigation surface.
- **No per-stop detail sheet beyond the native MapKit callout** — tapping
  a pin shows order + name (+ day, for multi-day itineraries) in the
  standard callout bubble; there's no custom bottom sheet with visit
  duration, arrival time, etc. (that information already lives in the day
  list directly below the map — the callout deliberately doesn't
  duplicate it).
- ~~**Day-selector chips only filter/refit the map**, not the day list
  below it — the two are intentionally independent.~~ **Superseded by
  v7.** As of "Bidirectional Itinerary ↔ Map Interaction" below, the map
  and the itinerary day/stop list share one `OptimizerSelection` and do
  react to each other — tapping a day chip still only affects the map
  directly (it doesn't scroll the list), but tapping a *stop*, in either
  place, now does keep both in sync. Left struck through rather than
  deleted for historical accuracy about what v5 shipped.
- **No route-distance/time overlay on the map itself** — total distance
  and travel time already appear in `OptimizerScoreBadge` immediately
  below the map; the map's polylines aren't separately labeled with
  per-segment distances.

## Assumptions / limitations (v6 — Real Road Route Visualization)

See "Real Road Route Visualization → Known limitations" above for the
full list (cache scoped per-screen-instance and not persisted;
`.automobile`-only transport type; no per-segment retry UI; no explicit
`MKDirections` rate-limiting/backoff; offline/Simulator behavior degrades
to v5's straight-line rendering by design, not as a bug).

## Assumptions / limitations (v7 — Bidirectional Itinerary ↔ Map Interaction)

- ~~**No persistence of the selection across screen visits.**~~ **Resolved
  in v13** ("Persistent Optimizer Map Selection" below) — session-scoped
  (not cross-launch) persistence now exists, keyed per itinerary.
- **Selecting a stop does not deep-link into `TravelTipsSection` or any
  other non-map, non-list content.** The shared selection only connects
  the map and the itinerary day/stop list — it has no relationship to,
  and does not affect, `OptimizerScoreBadge`, `ItineraryWarningsSection`,
  or the apply flow.
- **No multi-stop selection / comparison.** `OptimizerSelection.stopID`
  holds at most one stop at a time — tapping a second stop replaces the
  first, it never accumulates a set. A "compare two stops" or
  "select a range" interaction, if ever needed, would be a materially
  different feature, not a small extension of this one.
- **The callout button ("Apple Haritalar'da aç") and the new marker-tap
  focus behavior share the same tap target region on a small marker** —
  tapping the marker glyph itself selects/focuses (this milestone);
  tapping the callout's trailing accessory button (which only appears
  *after* the marker is already selected) opens Apple Maps (unchanged
  since v5). This two-step affordance (tap once to focus, tap the
  button that then appears to leave the app) is standard MapKit callout
  behavior, not a new interaction pattern introduced here.
- **Deselecting a stop by tapping empty map space is native MapKit
  behavior** (via `MKMapView`'s own deselect-on-background-tap) and does
  **not** clear `OptimizerSelection.stopID` — the itinerary row stays
  highlighted until a different stop or day chip is tapped. This
  mirrors `TripMapView`'s own precedent (its `focusedPin` mechanism has
  the identical asymmetry) rather than introducing new behavior, but is
  worth calling out as a deliberate non-symmetry: MapKit deselection is a
  map-only visual event, not a selection-clearing one.

## Assumptions / limitations (v8 — Preferred Start/End Time Controls)

- ~~**No overnight ranges** — `isTimeRangeValid` requires `start < end`
  within a single day...~~ **Resolved by v14** ("Overnight Time Ranges"
  below) — core-api's shared time-window model gained midnight-crossing
  support end-to-end, and `isTimeRangeValid` now only rejects equal
  values.
- ~~**No date or timezone selection** — `start_date` remains unexposed on
  iOS.~~ **Superseded by v9.** `start_date` is now exposed via "Planlama
  Tarihi" (see "Trip Planning Date" below); timezone selection remains
  out of scope, and — per v9's own finding — the entire system has no
  timezone concept to select from in the first place. Left struck through
  for historical accuracy about what v8 shipped.
- **No per-place opening-hours preview in the config screen** — the
  helper text explains that opening hours are a separate, place-level
  constraint, but doesn't show any specific place's hours (that data,
  `PlaceInput.opening_hours`, is core-api-only and not returned by any
  endpoint iOS calls at configuration time). Purely informational text,
  not a missing feature this milestone was asked to build.
- **No persistence of the chosen times across screen visits** —
  `TripOptimizerConfigViewModel` is created fresh (defaults restored)
  every time the config screen opens, same "no persistence of UI-only
  state" pattern already established for place selection and duration
  (see "Assumptions / limitations (v4)").
- **`DatePicker`'s `.compact` style is the only style used** — no
  `.wheel`/`.graphical` alternative was evaluated or offered; `.compact`
  was chosen as SwiftUI's default, standard, space-efficient style for a
  single HH:MM value in a scrollable form, matching the spec's own
  mockup shape.

## Assumptions / limitations (v9 — Trip Planning Date)

- **No timezone selection or awareness** — deliberately; see "Trip
  Planning Date → E. Timezone behavior" above. Nothing in the backend
  domain has a timezone concept, so this milestone doesn't invent one.
- **No date selection for `.viewSaved` mode** — reopening a saved
  itinerary shows whatever planning date it was generated with (if any);
  there's no way to change or add a date after the fact without
  generating a new itinerary. Consistent with this feature's own standing
  rule that `.viewSaved` never re-runs optimization.
- **No past-date restriction on the picker** — core-api doesn't validate
  that `start_date` is today or later (only that it's a well-formed ISO
  date), so the iOS `DatePicker` doesn't impose one either — restricting
  the client beyond what the server actually enforces would be an
  invented rule, not a reflected one.
- **No persistence of the chosen date across screen visits** — same
  "fresh `TripOptimizerConfigViewModel` every time" pattern already
  established for every other config field (see "Assumptions /
  limitations (v4)").
- **Map day-selector chips still read `"1. Gün"`/`"2. Gün"`, not real
  dates** — `OptimizerRouteMapSection`'s day chips (see "Map
  Visualization") were deliberately left unchanged; extending
  `OptimizerMapDay`/`OptimizerRouteMapData` to carry `date` through to the
  map's own UI would be a small, natural follow-up, but wasn't required
  by this milestone's stated scope (the day/stop *list* is the primary
  "itinerary" surface the requirements named). **Done in v10** — see
  below.
- **No recurring trips, no calendar integration** — explicitly out of
  scope (Req 15); a single optional date, nothing more.

## Assumptions / limitations (v10 — Date-aware Map Day Selector)

- **Still no timezone or date-arithmetic concept added on iOS** — the
  chip's date comes straight from `ItineraryDay.date`, itself just a
  passthrough of core-api's `start_date`-derived string (see "Trip
  Planning Date"). iOS only parses `"YYYY-MM-DD"` and formats it for
  display; it never computes, offsets, or validates a date range itself.
- **No date shown for `.viewSaved` itineraries generated before v9** —
  same fallback as everywhere else this field appears: a saved itinerary
  with no persisted `start_date` simply has `date == nil` per day, so its
  map chips render the pre-v10 `"1. Gün"`/`"2. Gün"` ordinal label,
  unchanged from before this milestone.
- **Chip label omits the year even across a trip spanning a New Year's
  Eve** — `chipLabel`/`chipAccessibilityLabel` show day+month only,
  never a year, by design (Req 1's explicit "no year" preference, chosen
  for the chip's limited horizontal space). A multi-year trip would show
  two visually-identical month/day labels for what are actually different
  years; this is an accepted, intentional constraint of the chip's small
  footprint, not an oversight — the itinerary list's own
  `ItineraryDay.formattedDate` (`"12 Ağustos 2026"`) already includes the
  year for exactly this reason and remains the authoritative full display.
- **No calendar integration, no navigation, no map redesign** —
  explicitly out of scope (Req 12); this milestone is a label-formatting
  change only.

## Assumptions / limitations (v11 — Persistent Optimizer Route Cache)

- **Not persisted across app launches, by design** — the cache is
  in-memory only and empties when the app process ends. Every entry is
  cheaply recomputable (one `MKDirections` request), so this trade-off
  was deliberate, not a shortcut; see "Persistent Optimizer Route Cache →
  Cache lifetime" above for the full reasoning against disk persistence.
- **Bounded at 500 legs (LRU)** — a session that genuinely revisits
  enough distinct itineraries/days to exceed this would start evicting
  the least-recently-used legs, re-requesting them on next access. This
  is an intentional, documented trade-off (Req 11 "do not create an
  unbounded cache"), not expected to matter for realistic single-session
  usage.
- ~~**Transport mode isn't part of the cache key**~~ **Resolved in v12**
  ("Optimizer Route Transport Mode → Cache correctness — CRITICAL" below)
  — `legKey`/`cacheKey` now include `mode=<mode>`.
- **In-flight requests remain screen-scoped, not shared** — two
  simultaneously-open screens showing the same itinerary each make their
  own in-flight request rather than awaiting one shared task; only
  *completed, successful* results are shared. Req 10 explicitly permitted
  this simplification.
- **No cache invalidation on `applyToTrip`** — applying a saved itinerary
  to the Trip doesn't touch this cache (nor should it: applying doesn't
  change the itinerary's own stops/coordinates, only the Trip's canonical
  `TripStop` list, and the two are already documented as intentionally
  decoupled — see "Apply to Trip"). Nothing about this milestone changes
  that boundary.
- **No user-facing cache indicator or manual "clear cache" control** — a
  cache hit is invisible by design (Req 16 "no new loading UI"); there is
  correspondingly no way for a user to force a fresh route recalculation
  short of the existing implicit invalidation triggers (a changed stop
  order/coordinate set, or the app process restarting).

## Assumptions / limitations (v12 — Optimizer Route Transport Mode)

- ~~**No Transit mode**~~ **Resolved in v18** — see "Transit Transport
  Mode" above.
- **Selected mode isn't persisted across screen visits** — `selectedTransportMode`
  is plain `OptimizerRouteMapSection` `@State`, defaulting to `.automobile`
  every time the section is freshly created. Consistent with how
  `OptimizerSelection` (v7) already behaves for day/stop focus, and
  explicitly required by this milestone's own scope exclusions ("do not"
  add `UserDefaults`/persistent storage for this).
- **No separate visual style for driving vs. walking routes** — both draw
  with the exact same polyline styling `OptimizerRouteMap` already used
  (color-per-day, solid for a real route, dashed for straight-line
  fallback). Explicitly required by the milestone spec ("do not add
  separate colors for driving vs walking") — the transport chip itself is
  the only place the current mode is visually indicated.
- **No cache size increase accounting for multiple modes** — `OptimizerRouteCache`'s
  LRU capacity (500 legs, unchanged from v11) is shared across whatever
  mix of driving/walking/transit (as of v18) entries a session
  accumulates, rather than each mode getting its own allowance. A user
  who toggles modes heavily across many itineraries in one session could
  see earlier entries evicted somewhat sooner than in a mode-unaware
  world; not judged significant enough to warrant a larger or
  per-mode-partitioned cache.
- **No manual retry, rate-limiting, or offline-behavior changes** — all
  unchanged from v6/v11 and apply identically regardless of which mode is
  selected; see "Real Road Route Visualization → Known limitations" above.

## Assumptions / limitations (v13 — Persistent Optimizer Map Selection)

- **Session-scoped only, not persisted across app launches** —
  `OptimizerSelectionStore` is in-memory, exactly like `OptimizerRouteCache`
  (v11); force-quitting the app (or the OS reclaiming it in the
  background) loses every stored selection. Deliberate, per Req 1 —
  explicitly not the same thing as "remembered forever," and not intended
  to be.
- **Unbounded storage, no LRU** — unlike `OptimizerRouteCache`'s 500-leg
  cap, `OptimizerSelectionStore` never evicts. Each entry is two optional
  scalar values, so even a session touching hundreds of itineraries costs
  a trivial amount of memory; a bound was judged unnecessary complexity
  for this milestone rather than an oversight.
- **"Follow the stop to its new day" is validated by the algorithm but not
  currently reachable in practice.** `ItineraryStop.id` bakes the day
  index into its own value (`"<dayIndex>-<orderIndex>-<placeID>"`), and a
  given `Itinerary.id`'s `days`/stops are immutable once created (nothing
  in this app edits a persisted itinerary in place — see "Trip Planning
  Date" and "Itinerary History" for why a *regenerated* itinerary is
  always a brand-new `Itinerary.id`, which starts with no stored selection
  at all rather than a stale one). `resolveSelection`'s "search all days,
  not just the stored one" logic is still correct, tested, and kept as
  defensive validation — but under this app's current architecture, a
  stop's `id` cannot actually change days for a *fixed* itinerary id, so
  the "moved to another day" path and the "nothing moved" path are, today,
  the same outcome by construction.
- **No user-facing indicator that a selection was restored** — matching
  Req 16/v11's own "no new loading UI" precedent, restoration is silent:
  the map and itinerary list simply open already focused on the right
  day/stop, with no toast, banner, or animation calling attention to it.
- **`applyToTrip` does not touch the selection store** — applying a saved
  itinerary to the Trip has no relationship to which day/stop was focused
  on the map, and this milestone didn't create one; see "Persistent
  Optimizer Map Selection → Interaction with the route cache and
  transport mode" above for the analogous route-cache boundary.

## Assumptions / limitations (v14 — Overnight Time Ranges)

- **No visual "overnight" indicator anywhere on iOS** — the config
  screen's two `DatePicker`s don't show a "+1 day" badge or similar when
  the selected range wraps midnight, and the itinerary day list/map day
  chips don't distinguish an overnight day from a same-day one. A stop
  scheduled at `"01:00"` displays identically whether that's 1 AM the same
  calendar day or the day after — matching "Overnight Time Ranges → What
  iOS deliberately does not compute" above; not judged worth a UI
  affordance for this milestone.
- **No client-side preview of which places are actually reachable** under
  a chosen overnight window — iOS has no visibility into any place's
  `opening_hours` before generating (it never has, this predates this
  milestone), so a user picking `18:00 → 01:00` has no client-side signal
  about which of their selected places will end up scheduled, conflicted,
  or excluded; that's only knowable after the request completes, exactly
  as with every other scheduling outcome.
- **`ClockTime` gained no overnight-aware API** (`isOvernight`, `duration`,
  or similar) — deliberately, see "Overnight Time Ranges → What iOS
  deliberately does not compute" above; introducing one would duplicate
  server-side logic for no client-visible benefit.
- **Timezone remains entirely absent**, unaffected by this milestone —
  see `docs/trip-optimizer.md` "Overnight Time Ranges → Timezone: still
  none."

## Assumptions / limitations (v15 — Persistent Optimizer Configuration)

- ~~**Map-side transport mode changes don't write back into the store**~~
  **Resolved in v16** — see "Persistent Optimizer Transport Mode Sync"
  above.
- **Session-scoped only, not persisted across app launches** —
  `OptimizerConfigurationStore` is in-memory, exactly like
  `OptimizerRouteCache`/`OptimizerSelectionStore`; force-quitting the app
  loses every stored configuration. Deliberate, matching the identical
  choice made for both prior stores.
- **No user-facing indicator that a configuration was restored** — the
  screen simply opens already configured, silently, matching the
  `OptimizerSelectionStore` (v13) precedent.
- **Duration clamping is defensive, not currently reachable** — the
  ViewModel's own `incrementDuration`/`decrementDuration` never let
  `durationDays` leave `[1, 30]` or `nil` in the first place, so a saved
  value ever needing clamping on restore would require external
  tampering with the store; the clamp exists for robustness (never blindly
  trust stored data), not because today's UI can produce an out-of-range
  value.

## Assumptions / limitations (v16 — Persistent Optimizer Transport Mode Sync)

- **A map-only mode change, before any config-screen visit, seeds
  `selectedPlaceIDs` from the currently-displayed itinerary, not an
  arbitrary "all trip places."** If the trip has since gained places that
  weren't in the itinerary the user was looking at when they changed the
  mode, those new places won't be part of that fallback selection — the
  same "reconciliation never invents selections the user didn't make"
  principle v15 already applies elsewhere, just triggered from a
  different entry point.
- **Still session-scoped only, not persisted across app launches** —
  `OptimizerConfigurationStore` itself wasn't changed in this regard;
  force-quitting the app loses every stored configuration, transport mode
  included, exactly as before.
- **No user-facing indicator that a map-side mode change was saved** — the
  chip simply changes selection state, with no toast/confirmation, same
  precedent as every other silent-persistence point in this store.

## Assumptions / limitations (v17 — Optimizer Configuration Transport Mode Picker)

- **No user-facing indicator that the picker's change was saved** — same
  precedent as every other silent-persistence point in this store (v13,
  v15, v16); the segmented control simply reflects the new selection.
- **Still session-scoped only, not persisted across app launches** —
  nothing about persistence lifetime changed; this milestone only added a
  new caller of the existing store.
- **The picker's fallback-selection edge case (v16) is unchanged** — if
  the config screen is opened for the first time *after* a map-only mode
  change already created a configuration entry, the picker (like every
  other field on this screen) shows whatever v16's fallback logic
  restored; this milestone didn't touch that logic, only added a UI that
  reads/writes the same field once the screen is open.

## Assumptions / limitations (v18 — Transit Transport Mode)

- **No schedule-aware transit routing.** No `departureDate`/`arrivalDate`
  is passed to `MKDirections` — a transit route, when found, reflects
  "depart now," not the optimizer's own planned day/time
  (`planningDate`/`preferredStartTime`/`preferredEndTime` never reach
  `MKDirectionsRoutingProvider`). Investigated and deliberately deferred —
  see "Transit Transport Mode → Transit-specific request configuration"
  above; threading a routing timestamp through would be a separately
  scoped milestone.
- **Transit availability is inherently inconsistent.** Coverage depends
  entirely on Apple Maps' own regional transit data — some cities/regions
  have rich data, others have none. A missing transit route is expected,
  common, and handled entirely by the pre-existing (v6) straight-line
  fallback; it is not a bug and does not degrade any other mode.
- **No live transit routing was exercised in this environment** — see
  "Transit Transport Mode → Simulator / live verification" above; only
  the deterministic, provider-mocked failure/fallback path was verified.
- **Map transport selector now scrolls at three options** — a small,
  existing-pattern (`daySelector`) adjustment; no visual redesign.

## Assumptions / limitations (v19 — Delete Saved Itinerary from History)

- **No undo.** Deletion is immediate and permanent once confirmed — no
  soft-delete, trash/recovery window, or undo toast. The confirmation
  dialog is the only safeguard, matching `TripDetailView`'s own trip-delete
  precedent (also no undo).
- **No bulk delete.** One itinerary at a time, via swipe — no
  select-multiple/"Edit" mode on this screen.
- ~~**No apply-history awareness beyond the single `applied_itinerary_id`
  pointer.**~~ **Resolved in v20** — see "Apply History & Undo" above.
- **The full interactive delete flow (swipe → confirm → row disappears,
  including the applied-itinerary and currently-open-detail-screen
  scenarios) was not exercised live** — see "Delete Saved Itinerary →
  Test results" above; verified via 299 iOS + 503 core-api + 107 Mobile
  BFF + 64 Web BFF deterministic tests instead.

## Assumptions / limitations (v20 — Apply History & Undo)

- **No apply-history retention/pruning.** `trip_itinerary_apply_history`
  grows one row per apply/undo, forever, with no cap or archival — see
  `docs/trip-optimizer.md` "Future improvements". Not a practical concern
  at current usage scale.
- **No pagination on the history list.** `GET .../itinerary-apply-history`
  returns every row for the trip in one response; a trip with hundreds of
  applies would return a proportionally large payload. Same "not a
  practical concern yet" judgment as retention above.
- **Undo-of-undo ("redo") works mechanically but has no dedicated UI
  label.** Undoing an entry that is itself an undo correctly restores the
  pre-undo state (see "Why this symmetry matters" in
  `docs/trip-optimizer.md`) — the row just still says "Geri Al," not
  "Yinele"/"Redo," because it's the same uniform action either way.
- **The `hasApplyHistory` toolbar flag doesn't refresh after a fresh
  apply/undo within the same screen session** — inherited, unmodified,
  from `hasItineraryHistory`'s own identical pre-existing limitation (see
  "UI: a new toolbar entry point" above); a first-ever apply's toolbar
  icon appears only after the screen is next freshly mounted.
- **The full interactive apply/undo flow was not exercised live** — see
  "Apply History & Undo → Test results" above; verified via 1035
  deterministic tests across all four suites instead.

## Future UI improvements

Ranked by what unlocks the most value next:

1. ~~**Delete a history entry**~~ **Resolved in v19** — see "Delete Saved
   Itinerary" above.
2. ~~**Apply history / undo**~~ **Resolved in v20** — see "Apply History &
   Undo" above.
3. ~~**Web UI**~~ **Resolved in v21** — see `docs/web-trip-optimizer.md`.
   The web map uses straight-line polylines, not a MapKit-equivalent
   routing implementation — that remains a documented limitation there,
   not a gap in this milestone.
4. **Bulk selection by category/city** — see "Assumptions / limitations
   (v4)" above.
5. ~~**A transport-mode picker on the config screen itself**~~ **Resolved
   in v17** — see "Optimizer Configuration Transport Mode Picker" above.
6. ~~**Transit transport mode**~~ **Resolved in v18** — see "Transit
   Transport Mode" above.
7. **Schedule-aware transit routing** — see "Assumptions / limitations
   (v18)" above; would require threading a routing timestamp through
   `OptimizerRoutingProviding`, the calculator, and (likely) the cache
   key — a genuinely separate, larger milestone.
8. **A dedicated "Redo" affordance** — see "Apply History & Undo →
   Assumptions / limitations" above; undo-of-undo already restores the
   correct state, just isn't labeled distinctly.
9. **Apply-history retention/pruning and list pagination** — see "Apply
   History & Undo → Assumptions / limitations" above.
