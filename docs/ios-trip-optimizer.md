# iOS — AI Trip Optimizer

The iOS UI for the [AI Trip Optimizer](trip-optimizer.md), consuming the
[Mobile BFF proxy](trip-optimizer-bff.md) exclusively. Lets a user
generate a preview itinerary from an existing Trip Builder trip's stops,
and revisit any previously generated one — never mutates the trip itself.

Eight milestones so far:
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
- **v8 — Preferred Start/End Time Controls** (this update): the
  `TripOptimizerConfigView` gains two time pickers — the optimizer's
  existing `preferred_start_time`/`preferred_end_time` fields, already
  used server-side since the very first optimizer milestone but never
  before sent by iOS, are now real, user-editable, client-validated
  inputs that reach every generate request. See "Preferred Start/End Time
  Controls" below.

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

### Validation (Req 4)

```swift
var isTimeRangeValid: Bool { preferredStartTime < preferredEndTime }
var canOptimize: Bool { !selectedPlaceIDs.isEmpty && isTimeRangeValid }
```

Mirrors core-api's own rule exactly — `preferred_end_time` must be
*strictly* after `preferred_start_time` (equal is rejected too, matching
`OptimizationService`'s `<=` check, not `<`). `canOptimize` — the same
property that already gated the "Optimize Et" button on a non-empty place
selection since v4 — now gates on **both** conditions; no new
disablement mechanism was introduced, the existing one was extended
(reused per Req 10/11). The bottom bar's message distinguishes which
condition is failing (`"En az bir mekan seçmelisin"` vs. `"Başlangıç
saati bitiş saatinden önce olmalı"`) rather than a single generic
"invalid" string, so the user always knows what to fix without guessing.

**No auto-correction.** Changing the start time never touches the end
time and vice versa (`setPreferredStartTime`/`setPreferredEndTime` each
write exactly one property) — if that produces an invalid range, the UI
surfaces it and blocks "Optimize Et" rather than silently nudging the
other value. This was a deliberate choice, not an oversight: the same
"structural, not corrective" philosophy the duration stepper already
uses (it clamps at its own bounds rather than reaching into unrelated
state), and it's exactly what the spec's own test list requires
("changing only the start time doesn't modify the end time").

**Overnight ranges are out of scope**, per the spec's explicit exclusion
— `isTimeRangeValid` requires `start < end` within a single day, with no
wraparound. This isn't an arbitrary iOS-side restriction: core-api's
shared `_parse_opening_hours` (used by both strategies for place opening
hours) doesn't support midnight-crossing ranges either (see
`docs/trip-optimizer.md` "Future improvements" → `_parse_opening_hours`
overnight support), so an overnight *preferred* window would be
inconsistent with a constraint the backend can't yet honor either way.

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
  (`route(from:to:) async throws -> [CLLocationCoordinate2D]`) that is
  the *only* seam between the calculator and `MKDirections`. This exists
  specifically because `MKRoute` has **no public initializer** — Apple's
  own type can only ever be produced by a real `MKDirections` call, which
  makes it impossible to construct a fake `MKRoute` for tests. Testing the
  protocol instead of the concrete MapKit type is what makes the
  orchestration logic testable at all (see "Testing" below).
- **`MKDirectionsRoutingProvider`** — the one production conformer;
  builds an `MKDirections.Request` (`.automobile` transport, per Req 1's
  own "driving route geometry" wording), awaits
  `MKDirections(request:).calculate()` (Swift's automatic async/await
  bridging over the completion-handler API — no manual continuation
  wrapping needed), and extracts the winning route's coordinates.
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

### Caching

Keyed by `OptimizerRouteCalculator.cacheKey(for:)` — `"day=<index>|<stopID>@<lat>,<lng>|…"`
for every stop in that day, in order (Req 6's own "day + ordered stop
IDs/coordinates" wording, satisfied literally). Reordering, a different
day index, or a different stop set all produce a different key, so the
cache can never serve a stale sequence as if it were current.

**Scope: per-screen-instance, not persisted across app sessions or
re-opens.** `OptimizerRouteMapSection`'s `@State private var calculator`
is recreated whenever the section's own view identity is recreated (a
fresh `TripOptimizerView` navigation push). This is a deliberate,
documented choice, not an oversight — see "Known limitations" below.
Within a single screen visit, though, the cache is exactly what prevents
request churn: switching from Day 1 → Day 2 → back to Day 1 only ever
issues Day 1's requests once (see
`test_load_calledTwiceForSameDay_secondCallUsesCache_noNewRequests`), and
selecting "Tümü" after having already viewed individual days reuses every
day's already-cached result rather than re-requesting anything.

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

- **Cache is per-screen-instance, not persisted.** Reopening the same
  itinerary later (a fresh `TripOptimizerView` push, even for the exact
  same `Itinerary`) recomputes every route from scratch. This was a
  deliberate scope decision — a cross-session cache would need a storage
  layer (disk or a shared in-memory singleton with its own invalidation
  rules) that this milestone's stated scope ("keep architecture,
  preserve async behavior within a screen visit") didn't call for. See
  "Future UI improvements" below.
- **Transport type is fixed to `.automobile`.** No walking/transit toggle
  exists — Req 1 explicitly asked for "driving route geometry," so this
  matches the requirement as written, not an oversight.
- **No manual retry for a failed leg.** A leg that fails once stays a
  straight-line fallback for the rest of that screen visit (it's cached
  as such) — there's no "tap to retry this segment" affordance. Given
  `MKDirections` failures are usually either "no route exists" (retrying
  won't help) or a transient network blip (retrying the whole day, e.g.
  by leaving and reopening the itinerary, does help), a per-segment retry
  UI wasn't judged worth the added surface for this milestone.
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
- **`OptimizerRouteMapData`** (v5; gained `stop(withID:)` in v7) — pure
  `Itinerary` → per-day, coordinate-only presentation struct. No
  MapKit/SwiftUI dependency; see "Map Visualization" above.
  `stop(withID:)` is the stable-identity lookup (Req 3) the map's
  focus/select logic and the tests both use.
- **`OptimizerRouteMap`** (v5; gained `selectedStopID`/`onSelectStop` +
  a `didSelect` delegate method in v7) — the `MKMapView`/`UIViewRepresentable`
  itself, structurally a day-aware sibling of `TripMapView`.
- **`OptimizerRouteMapSection`** (v5; gained `OptimizerRouteCalculator`
  ownership + route-loading lifecycle in v6; gained `OptimizerSelection`
  binding ownership in v7, replacing its own local `selectedDayIndex`
  state) — the SwiftUI wrapper `TripOptimizerView` actually embeds:
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
- **`ItineraryDaySection`** (existed since v1; gained `selectedStopID`/
  `onSelectStop` + made every row an interactive, highlightable `Button`
  in v7) — previously pure display, now also reports taps upward and
  reflects the shared selection.
- **`ClockTime`** (new, v8, `Core/Models/ClockTime.swift`) — the
  type-safe hour/minute value type described in "Preferred Start/End Time
  Controls" above. Not a view; carries the preferred-time state through
  `TripOptimizerConfigViewModel`/`TripOptimizerViewModel`/`Endpoint`,
  converting to `"HH:MM"` only at the network boundary.

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

131 tests, eleven files:

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
- **`TripOptimizerViewModelTests.swift`** (29 tests: 26 through v7, plus 3
  new this milestone) — the original 10
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
- **`OptimizerEndpointTests.swift`** (14 tests: 11 through v4, plus 3 new
  this milestone) — networking tests, pure and synchronous:
  `Endpoint.urlRequest` path/method/body/`Authorization` header, plus
  JSON-decoding tests against realistic server payloads. `duration_days`
  is omitted from the body when `nil` (the default — byte-identical to
  every pre-v4 request), and included with the exact value when provided
  (v4). **3 new this milestone (v8)**:
  `test_optimizeTrip_bodyIncludesCustomPreferredStartAndEndTime` (both
  fields encode to the exact `"HH:MM"` string, zero-padded),
  `test_optimizeTrip_changingOnlyStartTime_leavesEndTimeAtDefault`, and
  `test_optimizeTrip_changingOnlyEndTime_leavesStartTimeAtDefault` — the
  request-encoding-level proof that each `ClockTime` parameter is
  independent. The two pre-existing body-shape tests
  (`test_optimizeTrip_bodyContainsSelectedPlaceIDs`,
  `test_optimizeTrip_bodyIncludesDurationDays_whenProvided`) had their
  `json.count`/field assertions updated to reflect that
  `preferred_start_time`/`preferred_end_time` are now always present
  (`1`→`3`, `2`→`4`) — see "Preferred Start/End Time Controls → Request
  wire format" above for why this is a deliberate, not accidental, change
  to those tests.
- **`TripOptimizerConfigViewModelTests.swift`** (28 tests: 17 from v4,
  plus 11 new this milestone) — pure local state, no `FakeAPIClient`
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
  values too, not just start > end), false when start > end; and —
  directly proving Req 4's "Optimize must not execute while the
  configuration is invalid" — `canOptimize` is `false` when the time range
  is invalid *even with a non-empty place selection* (isolating that the
  time check, not the place check, is what's blocking), and `true` when
  both conditions hold.
- **`ClockTimeTests.swift`** (11 tests, new this milestone) — pure
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
- **`OptimizerRouteMapDataTests.swift`** (19 tests: the original 13 from
  v5, plus 6 new this milestone) — pure `XCTest` against
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
  **New this milestone (`stop(withID:)`, Req 3/9/10)**: a stop's
  `stop(withID:)` result carries the exact same `id` as its source
  `ItineraryStop` (stable identity); it's found regardless of which day is
  currently the `visibleDays` filter target (`stop(withID:)` searches all
  `days`, not just the filtered subset — proving the map can resolve a
  Map→Itinerary or Itinerary→Map focus even for a stop outside the
  currently-selected day, which is exactly the Req 4 day-switch scenario);
  a missing-coordinate stop's ID returns `nil` (never found, never
  crashes); an unknown ID returns `nil`; the same lookup works identically
  against a saved-itinerary-shaped value; and a direct assertion that
  `ItineraryStop.id` (what row-highlight equality compares) is stable and
  non-empty even when `lat`/`lng` are both `nil`.
- **`Support/FakeOptimizerRoutingProvider.swift`** (new this milestone) —
  `OptimizerRoutingProviding` test double, same family as `FakeAPIClient`:
  records every `(from, to)` call, an injectable `resultProvider` closure
  for success/failure per call, and an optional `AsyncGate` for
  deterministic in-flight-state tests. Exists specifically because
  `MKRoute` has no public initializer (see "Real Road Route Visualization
  → Was MKDirections sufficient" above) — this fakes the *protocol*, never
  the concrete MapKit type.
- **`OptimizerRouteCalculatorTests.swift`** (14 tests, new this
  milestone) — `OptimizerRouteCalculator` against `FakeOptimizerRoutingProvider`,
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
  checked deliberately, not assumed).
- **`OptimizerSelectionTests.swift`** (6 tests, new this milestone) — pure
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

### Test results

```
Test Suite 'All tests' passed
Executed 131 tests, with 0 failures (0 unexpected) in 0.130-0.158s
```

Full `xcodebuild clean test` (a genuinely clean rebuild, not incremental)
also verified no new warnings — every warning present traces to
pre-existing, untouched files (`TripMapView.swift`/`OptimizerRouteCalculator.swift`
`MKPlacemark`/`MKMapItem` deprecations, a pre-existing nil-coalescing
warning in `TripOptimizerView.swift`'s error state, and a handful of
scattered warnings in Auth/Home/Library/Processing/AppDelegate files this
milestone never touched). This milestone made **no core-api, mobile-bff,
or web-bff changes** — see "Preferred Start/End Time Controls → Was a
backend/BFF change necessary? No" above — so no backend/BFF suite reruns
were required; the counts from the previous milestones' backend/BFF
suites stand unchanged.

Verified stable across repeated full-suite `xcodebuild test` runs,
including the clean rebuild — no flakes observed this milestone (the v6
`OptimizerRouteCalculatorTests` flake noted in earlier milestones' test
logs is a known, pre-existing, load-dependent sensitivity in that
specific async test family, unrelated to and untouched by this
milestone's changes).

A live Simulator launch-and-crash-free check was performed (install →
launch → screenshot of the initial screen, confirming the app — now
additionally containing two `DatePicker`s, the first in the project —
still boots and renders normally). A full interactive tap-through
(opening the config screen, adjusting both time pickers, confirming the
"Optimize Et" button disables on an invalid range and re-enables on a
valid one, generating a real itinerary against a running backend with
non-default preferred times, and confirming the resulting schedule
respects them) was **not** performed in this environment — same
limitation as every prior milestone's testing notes (no
XCUITest/accessibility automation harness here, and reaching this screen
requires a live backend + authenticated session + a real trip with
stops) — that level of verification relies on the 131 passing automated
tests (28 of them new this milestone, directly exercising default values,
independent start/end updates, range validation, request encoding, and
request forwarding) plus the clean build instead.

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

- **No persistence of the selection across screen visits.** `OptimizerSelection`
  is plain `TripOptimizerView` `@State` — reopening the same itinerary
  (even the exact same one, from Itinerary History) starts with no stop
  focused and no single day pinned ("Tümü"), same as every other
  `@State` in this feature area. Not addressed here, consistent with
  every prior milestone's own "no persistence of UI-only state" pattern
  (see e.g. "Assumptions / limitations (v4)").
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

- **No overnight ranges** — `isTimeRangeValid` requires `start < end`
  within a single day; deliberately, per the spec's own exclusion (see
  "Preferred Start/End Time Controls → Validation" above). Not addressable
  without core-api's shared `_parse_opening_hours` first gaining
  midnight-crossing support (already tracked in `docs/trip-optimizer.md`
  "Future improvements" independently of this milestone).
- **No date or timezone selection** — `ClockTime` is deliberately
  date/timezone-less; `start_date` remains unexposed on iOS exactly as it
  was before this milestone (out of scope per the spec's own exclusions).
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

## Future UI improvements

Ranked by what unlocks the most value next:

1. **Persist the route cache across screen visits** — today
   `OptimizerRouteCalculator`'s cache lives only as long as
   `OptimizerRouteMapSection`'s `@State` (see "Real Road Route
   Visualization → Known limitations"). A small keyed disk/memory cache
   (same `cacheKey(for:)` already used) would let reopening the same
   saved itinerary from Itinerary History skip re-requesting routes
   already resolved on a previous visit — a pure performance win, no
   behavior change.
2. **Walking/transit transport type toggle** — `MKDirectionsRoutingProvider`
   is hardcoded to `.automobile` (deliberately, v6's own scope; see
   "Known limitations"). Exposing `MKDirectionsTransportType` as a
   user-facing toggle would be a contained change, localized to that one
   type.
3. **Persist the selected day/stop across screen visits** — see
   "Assumptions / limitations (v7)" above; would need `OptimizerSelection`
   to move from plain `@State` to something durable (e.g. `UserDefaults`
   keyed by itinerary ID), a small, self-contained addition on top of the
   architecture this milestone put in place.
4. **Overnight preferred-time ranges** — blocked on core-api's shared
   `_parse_opening_hours` gaining midnight-crossing support first (see
   "Assumptions / limitations (v8)" above); a backend-first change, not an
   iOS-only one.
5. **Delete a history entry** — needs a new core-api `DELETE
   /internal/itineraries/{id}` (+ BFF proxy) first; today history is
   append-only.
6. **Apply history / undo** — `Trip.applied_itinerary_id` only tracks the
   most recently applied itinerary; there's no way to see or revert to an
   earlier apply. Would need a core-api apply-history table first (see
   `docs/trip-optimizer.md` "Future improvements").
7. **Web UI** — web-bff already exposes the full owner/editor surface
   including `apply` (parity with mobile-bff), but no web page calls any
   of it yet; every iOS-only milestone so far, including this one, has
   left it unaddressed. A web map visualization would need its own
   (non-MapKit) routing implementation entirely.
8. **Bulk selection by category/city** — see "Assumptions / limitations
   (v4)" above.
