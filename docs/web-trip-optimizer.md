# Web — AI Trip Optimizer

The web frontend's consumer of the [Trip Optimizer](trip-optimizer.md)
backend and its [Web BFF proxy](trip-optimizer-bff.md). Built entirely on
top of endpoints that already existed for iOS — no new optimization logic,
no second source of truth, no bypassing the Web BFF.

## Why a Trip Detail page had to be built first

Before this milestone, web had **zero** Trip Builder presence: no trips
list, no trip detail page, no trip API calls in `web/src/lib/api.ts`. The
optimizer needs *something* to attach to — a page that knows which trip
and which stops. Rather than either silently building a full Trip Builder
(create/reorder/delete stops — out of scope, iOS-only by design) or
silently skipping the gap, this was raised explicitly; the resolution was
a **minimal, read-only** Trip Detail page: enough UI to host the optimizer
entry point and the history/apply-history panels, nothing more. Trip
creation and stop editing remain iOS-only.

This is why `services/web-bff/app/routes/trips.py` (`GET /trips`,
`GET /trips/{id}`, read-only) exists — see
`docs/trip-optimizer-bff.md`'s "Web UI consumer" section for the BFF side.

## Routes

```
/trips                          — list (TripsPage)
/trips/[id]                     — detail: title, stops, entry points (TripDetailPage)
/trips/[id]/optimize             — config → generate, OR saved-itinerary view (OptimizePage)
/trips/[id]/optimize?itineraryId=N — saved mode: same route, GET-only load
/trips/[id]/history               — itinerary history list (ItineraryHistoryPage)
/trips/[id]/apply-history         — apply history + undo (ApplyHistoryPage)
```

### Why generate and saved-view share one route instead of two

iOS models this as two things: `TripOptimizerConfigView` pushes a
`TripOptimizerView` in `.generate` mode, or a saved itinerary is opened
directly in `.viewSaved` mode — two distinct screens on a navigation
stack. Web collapses this to **one route with local component state**
(`OptimizePageInner` in `src/app/trips/[id]/optimize/page.tsx`) instead of
two routes, because a generate config includes a `selected_place_ids`
array — serializing that into a URL to justify a second route would add
complexity for no benefit. The one piece of config-adjacent state that
*does* need to survive a link/bookmark — "which saved itinerary am I
looking at" — is carried the cheap way, as a single `?itineraryId=`
query param. When present, the config step is skipped entirely and the
itinerary is loaded via `GET /itineraries/{id}` only; `optimizeTrip()` is
never called in that path (see `handleGenerate`'s re-entrancy guard and
the saved-mode `Promise.all([getTrip, getItinerary])` branch in
`page.tsx` — there is no code path from saved mode into the mutating
`optimize` call).

## Deliberate deviation: no transport-mode selector

The milestone spec asked for a transport-mode selector ("automobile /
walking / transit... do not hardcode only two modes"). This was
deliberately **not built**, for two independent reasons that both point
the same way:

1. **The backend contract has never had this field.** Re-checking
   `OptimizeTripRequest` (`mobile-bff/app/routes/trip_optimization.py` and
   its core-api DTO) confirms `selected_place_ids`, `start_date`,
   `duration_days`, `preferred_start_time`, `preferred_end_time`,
   `strategy` — no `transport_mode`, ever. On iOS, transport mode is a
   purely client-side concept consumed only by
   `OptimizerRouteCalculator`/`MKDirectionsRoutingProvider` to *render* a
   route on the map; it has never been part of what gets optimized.
2. **The web map has no per-mode routing engine to make the choice mean
   anything** — see the next section. A selector that changes nothing
   about the rendered route would be non-functional UI theater.

`OptimizerConfigForm.tsx` documents this in its own comment; `TransportMode`
is still exported from `api.ts` (kept for a possible future use) but
nothing in the UI reads or writes it.

## Route map: straight lines only (permitted, documented limitation)

`OptimizerRouteMap.tsx` follows the exact precedent already set by
`MapPreview.tsx` (the Library map): dynamic client-only import of
`react-leaflet`/`leaflet`, dark CARTO tiles, and **straight-line polylines
between consecutive same-day stops** — there has never been a
routed-geometry backend on web (no MapKit/`MKDirections` equivalent), and
the milestone's own instructions explicitly permit this fallback rather
than requiring a new routing backend to be invented. Missing-coordinate
stops are excluded from the polyline/markers but counted and surfaced via
an explicit "Haritada gösterilecek konum yok" / partial-coverage notice —
never a silently broken map.

## Selection sync: single source of truth, no update loops

`OptimizerResult.tsx` owns `selectedDayIndex`/`selectedStopId` as local
state; the map and the stop list are both pure consumers — they read
props and call `onSelectStop`, they never hold their own copy of the
selection. This one-directional flow is what avoids the update-loop risk
called out in the spec: React doesn't re-invoke a click handler on a prop
change, so there's no feedback path for a loop to form.

Stop identity is **never** the array index. `stopId()` (exported from
`OptimizerRouteMap.tsx`) computes `` `${day_index}-${order_index}-${place_id ?? "deleted"}` ``
— deliberately the same formula as iOS's `ItineraryStop.id` computed
property, so a stop keeps a stable identity across day switches and
re-renders even if its position in an array changes.

## Map camera: selection-driven, not render-driven (Milestone 23)

The selection state described above already existed from Milestone 21 —
clicking a stop or a marker updated `selectedDayIndex`/`selectedStopId`
and both the map and the list re-rendered highlighted correctly. What was
missing, found by inspection rather than assumed, was **camera
movement**: `MapContainer`'s `center` prop only positions the map once at
mount (a known react-leaflet limitation — it doesn't reactively re-center
on prop changes), so selecting a stop from the itinerary list never
actually panned the map to it, and switching days never refit the view.

Two additions, both scoped to `OptimizerRouteMap.tsx`:

1. **`computeCameraTarget(days, selectedDayIndex, selectedStopId)`** — a
   pure function (no Leaflet dependency) that decides what the camera
   should do: focus the selected stop's coordinates if it has any (most
   specific), else fit the selected day's valid coordinates (a single
   point pans, multiple points `fitBounds`), else do nothing. Kept pure
   and exported specifically so it's unit-testable without mounting a
   real Leaflet map in jsdom — the same reasoning that already justified
   `stopId()` being a standalone export.
2. **`CameraController`** — a child of `MapContainer` that calls
   `useMap()` (react-leaflet's hook for the underlying Leaflet instance)
   and runs `computeCameraTarget` inside a `useEffect` keyed on
   `[selectedStopId, selectedDayIndex, days, map]`. Because the effect's
   dependencies are the selection values themselves, it only runs when a
   selection genuinely changes — never on every render, and never in
   response to the user's own manual pan/zoom (no map movement event is
   listened to, so there's no feedback path for a loop). `panTo` is used
   for single-point focus (smooth, keeps the user's current zoom level
   rather than jumping to a fixed one); `fitBounds` for multi-stop days.

**List follows map too**: `OptimizerResult.tsx` now scrolls the selected
stop's row into view (`scrollIntoView({ block: "nearest" })`) whenever
`selectedStopId` changes, via a container ref and a `data-stop-id`
attribute per row — satisfies "map marker → itinerary row scrolls into
view" without needing `Card` (the shared UI primitive) to support ref
forwarding, which it doesn't. jsdom doesn't implement `scrollIntoView`;
stubbed once in `vitest.setup.ts` (`Element.prototype.scrollIntoView`),
the standard fix for this jsdom gap.

**Day switching now clears a stale stop selection.** Previously the
day-tab buttons called `setSelectedDayIndex` directly; a stop selected on
day 1 stayed "selected" (harmlessly stale, matched nothing) after
switching to day 2. Replaced with a `selectDay()` helper that clears
`selectedStopId` only if it doesn't belong to the newly selected day's
scope — a stop still valid in the new day (e.g. switching from "Tümü" to
that stop's own day) stays selected, matching the spec's "preserve if it
belongs, clear if it doesn't."

**Missing coordinates**: `computeCameraTarget` treats a selected stop
with `lat`/`lng: null` as if nothing were selected for camera purposes
(falls through to the day-level fit, or does nothing) — the stop remains
selectable in the list (`aria-pressed` still flips), it simply never
produces a fake map target. A day with zero valid coordinates returns
`null` — the map's own pre-existing empty state ("Haritada gösterilecek
konum yok") already handles that, unchanged.

**Selected state is no longer color-only.** The itinerary stop rows'
selected style was previously a border/background tint alone; added a
small `Check` icon (shown only when selected) mirroring the exact pattern
`PlacesSelector.tsx` already uses for its own selection state — a shape
cue, not just hue, for users who don't perceive the color difference.
`aria-pressed` was already present for assistive tech and is unchanged.

**Nothing here calls the backend.** Selection (stop click, marker click,
day switch) is 100% local React state — no code path in `selectStop`,
`selectDay`, or `CameraController` calls any function from `api.ts`. This
holds identically in `generate` and `saved` mode, since both modes render
the exact same `OptimizerResult` component with the exact same selection
logic — saved mode's GET-only guarantee (established in Milestone 21) was
never touched.

## Apply, history, and apply-history/undo

- **Apply** (`OptimizerResult.tsx`): confirm dialog → `applyItinerary(id)`
  → re-entrancy guard (button disabled + in-flight check) while the
  request is outstanding → success banner or error toast, itinerary view
  never disappears on failure.
- **Itinerary History** (`ItineraryHistoryPage`): renders server order
  as-is (no client re-sort). Each row links to
  `/trips/{id}/optimize?itineraryId={itineraryId}` — GET-only, confirmed
  by both the unit test and a live end-to-end check against the running
  stack (see "Verification" below). Delete requires confirmation, then
  removes only that row from local state — no full reload.
- **Apply History / Undo** (`ApplyHistoryPage`): "Geri Al" is shown **only**
  when the server marks an entry `is_undoable: true` — this is never
  derived client-side. On a successful undo, the page does not locally
  guess the new state; it reloads history from the server (server is the
  only authority — see `docs/trip-optimizer.md` "Latest-only safety
  rule"). On `STALE_UNDO` (409) — the case where another apply/undo raced
  ahead of this one — the page shows a specific message and refreshes
  history, exactly as instructed, instead of attempting any local
  mutation. This branches on `ApiError.code === "STALE_UNDO"`, a new
  typed field added to `api.ts`'s error class specifically so callers can
  match on the machine-readable code rather than parsing Turkish message
  text.

## `ApiError`

`api.ts`'s `request()` used to throw a bare `Error`. It now throws
`ApiError extends Error` (`readonly code?: string; readonly status: number`),
fully backward compatible (`instanceof Error` still holds) — added because
the apply-history undo flow is the first place in the web codebase that
needs to branch on a specific error *code*, not just show a message.

## Testing

```bash
cd web && npm test
```

76 tests across 9 files, all passing together (not just individually) —
see "Hardening pass (Milestone 22)" below for the 7 added on top of the
initial 57, and "Map camera: selection-driven, not render-driven
(Milestone 23)" above for the 12 added on top of that (64 → 76): 6
`computeCameraTarget` cases (stop-over-day priority, missing-coordinate
fallback, single-point pan, multi-point bounds, empty day, no selection)
in `OptimizerRouteMap.test.tsx`, and 6 in `OptimizerResult.test.tsx`
(same-day preservation, day-switch clears an out-of-scope stop, day-switch
preserves an in-scope stop, missing-coordinate stop stays selectable,
selection never calls `applyItinerary`/the backend, saved-mode selection
sync).

- `OptimizerConfigForm.test.tsx` (10) — default-all-selected, toggle,
  select/deselect-all, zero-selection blocks submit, overnight range
  accepted, equal-time rejected, duration inc/dec, planning-date →
  `start_date`, stop-order-not-click-order, submit disabled while
  submitting.
- `OptimizerResult.test.tsx` (11) — score/warnings rendering, day
  switching, marker-click cross-day selection, missing-coordinates
  indicator, apply confirm/success/failure/re-entrancy, saved-mode badge.
- `ConfirmDialog.test.tsx` (5), `OptimizerRouteMap.test.tsx` (5 — `stopId`
  purity + safe pre-mount/empty states).
- `trips/page.test.tsx` (4), `trips/[id]/page.test.tsx` (6),
  `trips/[id]/history/page.test.tsx` (5), `trips/[id]/apply-history/page.test.tsx` (6),
  `trips/[id]/optimize/page.test.tsx` (5) — the page-level orchestration
  tests: loading/error/empty states, role-gated Optimize entry point,
  generate-mode request-body correctness, re-entrancy on duplicate
  submit, saved-mode GET-only load, delete/undo confirmation flows,
  STALE_UNDO handling.

### A test-infra gotcha worth recording

Every page renders the shared `Navbar`, which calls `usePathname()` — a
`vi.mock("next/navigation", ...)` that only stubs `useParams`/`useRouter`
throws ("No usePathname export is defined on the mock") the moment any
page-level test renders. Every page-level test file's `next/navigation`
mock must include `usePathname`.

A second, subtler one: `useRouter: () => ({ push })` — returning a *new*
object literal on every call — gives the page's own
`useEffect(..., [tripId, router])` a fresh `router` reference on every
render, so in a test environment (unlike real Next.js, where `useRouter()`
is stable) the effect re-fires and re-fetches on every render, racing
local state updates such as an optimistic delete. Symptom: a test passes
in isolation but fails intermittently as part of the full suite. Fix:
hoist the mock's returned object to a stable module-level constant
(`const router = { push }; ... useRouter: () => router`).

## Verification

Automated: `npm test` (57/57), `npx tsc --noEmit` (clean), `npm run lint`
(0 errors), `npm run build` (all 5 routes register correctly, static
where possible: `○ /trips`, dynamic: `ƒ /trips/[id]`,
`ƒ /trips/[id]/optimize`, `ƒ /trips/[id]/history`,
`ƒ /trips/[id]/apply-history`).

Live backend integration was also exercised end-to-end against the
running dev stack (register → seed a trip/stops/place-saves for a test
user → `GET /trips` → `GET /trips/{id}` → `POST /optimize` →
`GET /itineraries` → `POST /apply` → `GET /itinerary-apply-history` →
`POST undo` (success, then a second `undo` of the same entry confirming
`409 STALE_UNDO`) → `DELETE /itineraries/{id}`) — every response matched
the TypeScript interfaces in `api.ts` exactly. This caught two stale local
dev processes (web-bff not loading `CORE_API_URL` from `.env` when
started outside its usual launcher; core-api's Docker image predating the
apply-history feature and needing a rebuild) — both fixed by restarting
with the right environment / rebuilding the image, not a code change.

**What was not done:** interactive verification through the actual
rendered UI in a browser (click-through of the config form, the map, the
day tabs, the apply confirmation dialog). The Chrome browser automation
tool was unavailable in this environment (extension not connected). This
is a real gap, not a formality — the automated tests and the live API
checks above give strong confidence the data layer and page logic are
correct, but they do not confirm layout, responsiveness, or the map
actually rendering correctly on screen. A seeded test account
(`web-optimizer-verify@example.com`, trip id 2, "Gaziantep Gezisi") was
left in the local dev database specifically so this can be checked
manually in a browser.

## Future improvements

- Manual/automated browser verification of the actual rendered UI (see
  above — the one piece of the spec's verification requirements that
  couldn't be completed in this environment).
- If a real routing backend for the web map is ever built, apply the same
  per-mode rendering iOS has — until then, the transport-mode selector
  should stay omitted rather than added as inert UI.

## Hardening pass (Milestone 22)

A follow-up UX/reliability milestone with one rule: inspect first, only
touch what genuinely needed it. No business logic, API contracts, or
architecture changed — same routes, same Web BFF surface, same components.
Most of the spec's own checklist (configuration validation, saved-mode
GET-only behavior, day/stop/map sync, STALE_UNDO handling, responsive
day-selector, accessibility roles) was inspected and found already correct
from Milestone 21 — left alone, per the milestone's own instruction not to
create work for its own sake. Four things were genuinely fixed:

1. **Re-entrancy guards on apply/delete/undo.** `handleGenerate` already
   had an explicit `if (generating) return;` guard, but `handleApply`
   (`OptimizerResult.tsx`), `handleDelete` (history page), and
   `handleUndo` (apply-history page) relied *only* on the button's
   `disabled` attribute to prevent a second submission. That's normally
   enough — React re-renders and disables the button before any test
   harness fires a second event — but it leaves no defense-in-depth
   against a same-tick double-invocation. Added the same explicit guard
   (`if (applying) return;` / `if (deleting) return;` / `if (undoing)
   return;`) to all three, for consistency with the one handler that
   already had it, and added tests proving the underlying API function is
   still called exactly once under a pending-promise double-click.
2. **Sticky-bar overflow risk on narrow screens.** Both the config form's
   bottom bar and the result view's apply bar are
   `flex items-center justify-between` with a status text span next to a
   button — neither had `min-w-0`/`shrink-0`, so on very narrow viewports
   (320–375px) a long status string (e.g. "Başlangıç saati bitiş
   saatinden farklı olmalı") had no explicit permission to shrink/wrap
   against the button. Added `min-w-0` to the text, `shrink-0` to the
   button, on both bars — no layout change on normal widths, just a
   narrow-width safety net.
3. **A regression test guarding the no-transport-mode decision.** Nothing
   was broken here — this documents and locks in Milestone 21's
   deliberate omission (see above) so a future change can't silently
   reintroduce a non-functional transport-mode selector without a test
   noticing.
4. **Uncovered edge cases, now tested:** keyboard (Enter/Space) selection
   on a places-selector row and an itinerary-stop row (previously only
   click-tested); an invalid/deleted saved-itinerary ID showing the
   error+retry state instead of crashing; unmounting the optimize page
   while its initial load is still in flight not throwing.

Everything else the milestone asked to "verify" — already-applied
itinerary re-apply (idempotent, harmless, no UI change needed), long
place names/warnings (already `truncate`/wrap correctly), one-stop and
many-day itineraries, missing-coordinate map handling, `STALE_UNDO`
refresh behavior — was inspected and confirmed already correct, not
touched.

Test count: 64/64 (was 57/57) across the same 9 files, all still passing
together. `npx tsc --noEmit` clean, lint 0 errors, `next build` succeeds
with the same 5 routes. web-bff: 82/82, unchanged (no backend touched).

**Browser verification: still not performed.** The Chrome browser tool
remained unavailable in this environment for this milestone too — this is
reported honestly rather than assumed fixed. The three local dev
processes (Next.js on :3000, Web BFF on :8002, core-api on :8000) were
confirmed running and reachable so a human can check the actual rendered
UI directly.

## Interactive map ↔ itinerary sync (Milestone 23)

See "Map camera: selection-driven, not render-driven (Milestone 23)"
above for the full architecture writeup — this section covers what was
inspected, what was genuinely missing, and verification.

**Inspection first.** The bidirectional selection state itself
(`selectedDayIndex`/`selectedStopId` in `OptimizerResult.tsx`, stable
`stopId()` identity, unidirectional prop flow to the map and list) already
existed from Milestone 21 and was **not** rebuilt — clicking a stop
already highlighted it in the list and passed it to the map as
`selectedStopId`, and clicking a marker already called back into
`selectStop()`. What inspection found genuinely missing: the map's camera
never actually moved in response to a selection (react-leaflet's
`MapContainer` only honors its `center` prop once, at mount), the day
selector never cleared a now-out-of-scope stop selection, the itinerary
list never scrolled to reveal a marker-selected row, and selection state
communicated itself through color alone.

**Actual changes**: `computeCameraTarget()` + `CameraController` in
`OptimizerRouteMap.tsx` (camera pan/fit); a `selectDay()` helper replacing
the day-tab buttons' direct `setSelectedDayIndex` calls, so a stale
cross-day stop selection clears itself; a `scrollIntoView` effect keyed on
`selectedStopId` in `OptimizerResult.tsx`; a `Check` icon on selected stop
rows (non-color cue, mirrors `PlacesSelector`'s own pattern); a
`scrollIntoView` stub added to `vitest.setup.ts` (jsdom doesn't implement
it). No route, no Web BFF call, no core-api call, no new dependency — pure
client-side interaction, exactly as scoped.

**Tests**: 64 → 76/76, all passing together. web-bff: 82/82, unchanged
(nothing on the backend was touched, as required). `npx tsc --noEmit`
clean, lint 0 errors (same one pre-existing unrelated warning), `next
build` succeeds with the same 5 routes.

**Browser verification: not performed.** The Chrome browser tool was
checked again for this milestone and is still unavailable in this
environment — reported honestly, not assumed working. The local dev
stack (`localhost:3000`, Web BFF `:8002`, core-api `:8000`,
`web-optimizer-verify@example.com`, trip 2) remains live for manual
verification of the actual pan/fit/scroll/highlight behavior, which
automated tests can only verify at the logic level (`computeCameraTarget`'s
decisions, `aria-pressed`/`aria-selected` state, that `scrollIntoView` and
`applyItinerary` are/aren't called) — not that the map visually looks
right on screen.

**Known limitation**: `computeCameraTarget`'s decision logic is unit
tested directly; the actual Leaflet `panTo`/`fitBounds` calls inside
`CameraController` are not, because mounting a real Leaflet map in jsdom
is unreliable and the existing test file already established the
precedent of not doing that (its two `OptimizerRouteMap` component tests
only exercise the empty-state and pre-mount-placeholder paths). This
mirrors exactly how `stopId()` was already tested as a pure function
separately from the component — the same reasoning was extended here
rather than a new pattern invented.
