# iOS — AI Trip Optimizer (v1)

The first iOS UI for the [AI Trip Optimizer](trip-optimizer.md), consuming
the [Mobile BFF proxy](trip-optimizer-bff.md) exclusively. Lets a user
generate a preview itinerary from an existing Trip Builder trip's stops —
never mutates the trip itself.

## Screen flow

```
TripDetailView (existing)
  │  toolbar "sparkles" button — only shown when trip.allStops is non-empty
  │  NavigationLink(destination: TripOptimizerView(tripID:, placeIDs:))
  ▼
TripOptimizerView (new)
  │  .task { auto-triggers optimize on appear — no separate "Generate" tap }
  │
  ├─ loading  → ProgressView + "Gezi optimize ediliyor…"
  ├─ error    → destructive icon + server message + "Tekrar Dene" (retry)
  ├─ empty    → itinerary returned but itinerary.days.flatMap(\.stops) is empty
  └─ success  → OptimizerScoreBadge + ItineraryWarningsSection (if any) +
                ItineraryDaySection per day + "Daha Sonra İçin Kaydet" button

  toolbar leading "Kapat" — always available, in every state, dismisses immediately
```

`TripOptimizerView` never appears in Trip Builder's own flow unmodified —
it's a new destination reached from one new, conditionally-shown toolbar
button. `TripDetailView`'s existing map/stats/stop-list/edit/delete code is
untouched.

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
on the backend actually supports it yet (see `docs/trip-optimizer.md`
"Future improvements" — an explicit itinerary-history/apply screen is the
natural next step once this pattern needs to become real).

## ViewModel

`TripOptimizerViewModel` (`Features/Trips/TripOptimizerViewModel.swift`) —
deliberately byte-for-byte structurally identical to the existing
`TripDetailViewModel.load`, the established pattern for every ViewModel in
this app:

```swift
@Observable
@MainActor
final class TripOptimizerViewModel {
    private(set) var itinerary: Itinerary?
    private(set) var isLoading = false
    private(set) var error: APIError?

    func optimize(tripID: Int, placeIDs: [Int], auth: AuthEnvironment) async {
        guard !isLoading else { return }        // re-entrancy guard
        isLoading = true; error = nil
        defer { isLoading = false }

        guard let token = auth.user?.token else { return }

        do {
            itinerary = try await auth.apiClient.send(
                .optimizeTrip(tripID: tripID, placeIDs: placeIDs), token: token
            )
        } catch let apiError as APIError {
            if apiError.isUnauthorized { auth.handleUnauthorized(); return }
            error = apiError
        } catch {
            self.error = .unknown(statusCode: 0)
        }
    }
}
```

No separate "empty" flag: `TripOptimizerView` derives the empty state
itself from `itinerary.days.flatMap(\.stops).isEmpty` — the ViewModel just
carries whatever the server returned, same division of responsibility as
every other screen (e.g. `LibraryView` deriving its own empty/no-results
states from `vm.places`, not a VM-owned enum).

## API integration

Routes only through the Mobile BFF (`http://<host>:8001/api/mobile/...`)
— **never** talks to core-api directly, per the requirement. Three new
`Endpoint` cases (`Core/Network/Endpoint.swift`), following the exact
convention every other endpoint uses (central enum, not per-feature files):

| Case | Path | Method |
|---|---|---|
| `.optimizeTrip(tripID:placeIDs:)` | `/api/mobile/trips/{id}/optimize` | POST |
| `.itineraries(tripID:)` | `/api/mobile/trips/{id}/itineraries` | GET |
| `.itineraryDetail(itineraryID:)` | `/api/mobile/itineraries/{id}` | GET |

`.itineraries`/`.itineraryDetail` are wired into `Endpoint` now (ready for
the "Future improvements" itinerary-history screen) but this v1 UI only
calls `.optimizeTrip` — there's no history-browsing screen yet.

The POST body intentionally omits `start_date`/`duration_days`/
`preferred_start_time`/`preferred_end_time`/`strategy` — core-api's own
`OptimizeTripRequest` defaults apply (09:00–18:00, `greedy_distance`).
There's no date/duration picker in this v1; see "Future UI improvements."

New Codable models (`Core/Models/OptimizerModels.swift`) mirror core-api's
`OptimizeTripResponse` field-for-field (`Itinerary`, `ItineraryDay`,
`ItineraryStop`, plus `ItinerarySummary`/`ItineraryListResponse` for the
not-yet-used list endpoint), decoded via `APIClient`'s existing
`.convertFromSnakeCase` — no custom `CodingKeys` needed anywhere.

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

19 tests, three files:

- **`Support/FakeAPIClient.swift`** — `APIClientProtocol` test double.
  Returns a canned `Result<Any, Error>`; an optional `AsyncGate` (a small
  `actor` wrapping a `CheckedContinuation`) lets a test suspend `send`
  mid-flight on demand, for deterministic loading-state assertions.
- **`TripOptimizerViewModelTests.swift`** (10 tests) — ViewModel tests:
  initial state, success populates `itinerary`, server/network errors set
  `error`, a 401 logs the session out *without* setting `error` (matching
  `TripDetailViewModel`'s exact behavior), no-token short-circuits before
  ever calling the API. **Loading-state tests**: `isLoading` is
  observably `true` while the fake's `send` is parked on the gate and
  `false` immediately after, using `Task { await vm.optimize(...) }` +
  `Task.yield()` to let the child task reach its suspension point before
  asserting — plus a re-entrancy test confirming a second call while the
  first is still in flight is a true no-op (`callCount == 1` after both
  resolve).
- **`OptimizerEndpointTests.swift`** (9 tests) — **networking tests**,
  pure and synchronous, no ViewModel involved: `Endpoint.urlRequest`
  produces the right path/method/body/`Authorization` header for all
  three new cases, plus three JSON-decoding tests against realistic
  server payloads (including a null-`place_id` stop, for a deleted source
  Place — see `docs/trip-optimizer.md`).

### Test results

```
Test Suite 'All tests' passed
Executed 19 tests, with 0 failures (0 unexpected) in 0.037s
```

Full `xcodebuild build` (both `TripClipApp` and `TripClipShare` targets,
via the `TripClipApp` scheme, which builds both) also verified clean.

## Assumptions / limitations (v1)

- No date/duration/time-window picker — always uses core-api's defaults.
  A natural v2 addition once there's demand for it.
- No strategy picker — `greedy_distance` is the only strategy that exists
  server-side today anyway (see `docs/trip-optimizer.md`).
- The `.itineraries`/`.itineraryDetail` endpoints are wired but unused —
  there's no "view past itineraries for this trip" screen yet.
- The loading state's `ProgressView` doesn't rasterize correctly under
  `ImageRenderer`-based offline snapshotting (a tool limitation used only
  to produce this doc's screenshots, not a runtime issue — confirmed
  separately via a live Simulator launch that the real spinner renders
  normally, same `ProgressView` code already shipping elsewhere in the app).

## Future UI improvements

Ranked by what unlocks the most value next:

1. **Itinerary history screen** — a simple list backed by the
   already-wired `.itineraries(tripID:)` endpoint, so a user can revisit
   a "saved for later" itinerary instead of only seeing it once.
2. **Apply-to-trip action** — once there's a reason to actually commit an
   itinerary into `TripStop` (the backend explicitly deferred this, see
   `docs/trip-optimizer.md` "Future improvements" #2), add a real "Apply"
   button here — this v1 UI was scoped to preview-only on purpose.
3. **Date/duration/time-window controls** — expose the constraints
   core-api already accepts (`start_date`, `duration_days`,
   `preferred_start_time`/`preferred_end_time`) instead of always using
   its defaults.
4. **Place selection** — right now "Optimize Trip" always uses *all* of
   the trip's current stops; letting the user deselect a subset before
   generating (mirroring Library's own multi-select UI) is a reasonable
   next increment once the all-stops case has real usage.
5. **Map view of the optimized route** — `TripMapView` already exists and
   accepts a route polyline (used by `TripDetailView`); reusing it here to
   visualize the optimized order geographically is a low-effort addition.
