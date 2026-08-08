# AI Trip Optimizer (v1)

Generates a multi-day, time-windowed itinerary from places the user has
already saved to their Library — it never invents, geocodes, or extracts
new places. Given a `trip_id` and a subset of that trip owner's Library
(`selected_place_ids`), it orders them, splits them across days, estimates
arrival/departure/travel times, and persists the result as a versioned
`TripItinerary`.

## Scope

This is deliberately **not** a rewrite of Trip Builder's existing
`create_trip` (which does a single-day nearest-neighbor TSP pass and writes
directly to `TripStop`). It's a new, richer capability that sits next to
it: multi-day splitting, time windows, opening-hours awareness, warnings,
a quality score, and a persisted, versioned history of runs. Trip Builder
is untouched — see "Architecture" below for why the two don't share code.

## Architecture

```
app/domain/optimization/
    models.py     — PlaceInput, OptimizationConstraints, OptimizedStop/Day, OptimizationResult
    strategy.py    — RouteOptimizationStrategy (ABC)
app/domain/repositories/
    optimization_repository.py — AbstractOptimizationRepository (ABC)
app/infrastructure/optimization/
    greedy_distance_strategy.py — v1 strategy (nearest-neighbor + day-splitting)
    strategy_registry.py        — name → strategy instance, the extension point
app/infrastructure/repositories/
    sql_optimization_repository.py — SQLAlchemy implementation
app/application/
    dto/optimization_dto.py       — request/response Pydantic schemas
    services/optimization_service.py — validation, orchestration, dedup
app/api/internal/
    trip_optimization.py — POST /trips/{id}/optimize, GET .../itineraries, GET /itineraries/{id}
app/models/
    trip_itinerary.py, trip_itinerary_stop.py — persistence
    place.py — +opening_hours (nullable)
```

This mirrors the existing `domain/infrastructure/application/api` split used
by Trip Builder and Trip Sharing (see `sql_trip_repository.py`,
`sharing_service.py` for the same pattern).

### Why not reuse `app/ml/route_optimizer.py`?

The video pipeline already has a nearest-neighbor TSP solver
(`RouteOptimizer` in `app/ml/`), and `SqlTripRepository.create_trip` already
calls it. It would have been tempting to reuse it here. Deliberately
didn't, for two reasons:

1. **The requirement is explicit**: "Keep optimization independent from
   video processing, semantic search, place extraction." `app/ml/` is the
   video-pipeline's package (YOLO, Whisper, NER, the TSP solver — one file
   per pipeline stage). Importing from it would wire this bounded context
   to that one, even though the math itself is pipeline-agnostic.
2. **The interfaces don't match.** `RouteOptimizer.optimize_route` takes
   pipeline-shaped dicts (`{"original_name": ..., "place_data": {"location":
   {"lat", "lng"}}}`) and returns a flat single-day route with no day-
   splitting, time windows, or warnings — this feature needed all of those.

The cost of not reusing it is about 15 lines of duplicated haversine +
nearest-neighbor code inside `greedy_distance_strategy.py`. That's cheaper
than a cross-boundary dependency. Trip Builder's `create_trip` path is
completely untouched by this feature.

### Why itineraries aren't written into `TripStop`

`update_stop_order` (Trip Builder) treats `TripStop` as the trip's one
canonical stop list. If `optimize_trip` also wrote to `TripStop`, every
optimizer run would silently overwrite whatever the owner/editor had
manually arranged — and there'd be no way to compare two optimizer runs
against each other or against the manual arrangement. Instead, each
`optimize_trip` call creates a new `TripItinerary` + `TripItineraryStop`
rows, standalone from `TripStop`. Running the optimizer is always a safe,
non-destructive "preview" — nothing about the Trip Builder API's behavior
changes. See "Future improvements" for the natural next step (an explicit
"apply this itinerary" action).

## Algorithm ("simple heuristic" — v1: `greedy_distance`)

**Route-first, cluster-second.** Two passes over the (deduplicated,
ownership-checked) selected places:

1. **Route-first**: a single nearest-neighbor path across *all* selected
   places, ignoring day boundaries. Starting from the first place, always
   jump to the nearest unvisited one. This naturally clusters geographically
   close places next to each other in the path — including across multiple
   cities, since the algorithm only jumps to a new region once nothing
   closer remains in the current one.
2. **Cluster-second**: walk that single path in order, packing places into
   day-buckets against a per-day time budget (`preferred_start_time` →
   `preferred_end_time`, default `09:00–18:00`). A place that would push the
   day past `preferred_end_time` starts a new day instead — so
   `duration_days`, if omitted, is *derived* from how many days the
   selection actually needs, not guessed upfront by the caller.

Within the walk, a running time cursor tracks arrival/departure per stop:

- **Visit duration** comes from a small category → minutes lookup
  (`museum: 90, landmark: 30, restaurant: 60, park: 45, viewpoint: 20,
  shopping: 45`), falling back to 60 minutes for unknown/missing category.
- **Travel time** to the next stop is `haversine_km(a, b) / 25 km/h`, an
  assumed flat urban average speed (see "Assumptions").
- **Opening hours**, if present on the place (`"HH:MM-HH:MM"`, daily only):
  an arrival before opening is silently pushed to the opening time (this
  *is* "respecting" the hours, not a problem); an arrival at/after closing
  produces a warning but the stop is **not** rescheduled — see
  "Limitations."
- A segment ≥ 50 km between consecutive stops (a likely inter-city jump)
  produces a "long travel segment" warning.
- If `duration_days` was given and is smaller than what's needed, the
  optimizer does not drop any user-selected place. Everything that doesn't
  fit is appended to the final allowed day anyway, with a single warning —
  silently dropping a place the user explicitly selected would be worse
  than an overloaded last day.

### Optimization score

A transparent, deterministic 0–100 heuristic — not a validated quality
metric, just a cheap, explainable signal:

```
avg_km_between_stops = total_distance_km / max(1, stops - 1)
travel_penalty  = min(40, avg_km_between_stops * 2)
warning_penalty = min(30, len(warnings) * 5)
score = max(0, 100 - travel_penalty - warning_penalty)
```

Note: the "N duplicate place selection(s) removed" warning (added by
`OptimizationService`, after the strategy already scored the route) is
**not** included in this calculation — it's request hygiene, not a
property of the route itself. See `optimization_service.py`.

## Extension points

Adding a new strategy (Google Maps API, Apple Maps, OR-Tools, an
LLM-assisted planner, …) requires no change to the service, DTOs, or API:

1. Implement `RouteOptimizationStrategy` (`app/domain/optimization/strategy.py`)
   — one method, `optimize(places: List[PlaceInput], constraints) -> OptimizationResult`.
2. Register it: `register_strategy(MyStrategy())` in
   `strategy_registry.py`.
3. Callers select it via `OptimizeTripRequest.strategy` (e.g.
   `"or_tools"`) — `OptimizationService` resolves it by name and never
   imports a concrete strategy class itself.

A strategy backed by a real routing API would naturally also improve travel
time accuracy and could resolve opening-hours conflicts by actually
reordering stops — both flagged as v1 limitations below.

## Assumptions

- **Average travel speed: 25 km/h**, flat, no traffic/time-of-day model —
  an approximation to unblock v1 without a real routing engine. A
  Maps-API-backed strategy would replace this with actual drive/walk times.
- **Visit duration is category-based, not location-specific** — a small
  hardcoded lookup, not derived from real-world data (there is none yet:
  `Place.category` is not populated by any pipeline stage today, same as
  when it was added — see `place.py`). Every place effectively gets the
  60-minute default until category classification ships.
- **Opening hours are daily-only** (`"09:00-18:00"`), not per-weekday, not
  seasonal, and — as of this writing — **populated by no pipeline stage**.
  In practice every optimizer run today includes the "opening hours
  unavailable" warning for every place, exercised in tests but not yet a
  real signal in production data.
- **`selected_place_ids` are validated against the *trip owner's* Library**
  (`PlaceSave` rows for `Trip.user_id`), not the requesting collaborator's —
  matching how `Trip.create_trip` already resolves ownership. An editor can
  run the optimizer on the owner's places; they don't need their own copy
  of the same saves.
- **Only the trip owner and editor collaborators can run the optimizer**
  (`resolve_access` ∈ {owner, editor}); viewers can read persisted
  itineraries but not generate new ones — the same split as
  `update_stop_order`.

## Limitations (v1)

- **No re-shuffling for opening-hours conflicts.** If a stop's computed
  arrival lands after closing, the optimizer warns but keeps the stop where
  the greedy walk put it — it doesn't try a different day or a different
  position in the route. Real constraint-solving (which day/slot fits every
  stop's hours) is exactly the kind of problem an OR-Tools-based strategy
  would solve properly; deferred there on purpose rather than half-building
  a weaker version of it here.
- **No real-world travel time.** No traffic, no walking-vs-driving
  distinction, no public transit — flat haversine distance over an assumed
  speed. A Google/Apple Maps strategy is the natural fix.
- **The route-first/cluster-second split can be locally suboptimal.**
  Nearest-neighbor is a classic, well-known TSP heuristic — good enough for
  small selections, not close to optimal for larger ones (no 2-opt pass,
  no OR-Tools-grade solver). This is explicitly what "the first
  implementation may use a simple heuristic" calls for.
- **The optimization score is not comparable across strategies** or
  validated against real user satisfaction — it's a same-strategy,
  same-run diagnostic, not a benchmark.
- **No "apply to trip" action yet.** An itinerary is a standalone,
  persisted preview; nothing currently copies it into `TripStop`. See
  "Future improvements."

## API

All routes are internal (`verify_internal_secret`), proxied by a BFF the
same way Trip Builder/Trip Sharing are — no BFF route exists yet for this
feature (see "Future improvements": the highest-impact next step).

### `POST /internal/trips/{trip_id}/optimize`

Requires `x-user-id` header (owner or editor).

```json
{
  "selected_place_ids": [12, 7, 19],
  "start_date": "2026-09-01",
  "duration_days": 2,
  "preferred_start_time": "09:00",
  "preferred_end_time": "18:00",
  "strategy": "greedy_distance"
}
```

All fields except `selected_place_ids` are optional (defaults shown above).

```json
{
  "id": 4,
  "trip_id": 1,
  "strategy_name": "greedy_distance",
  "optimization_score": 87.5,
  "total_distance_km": 12.4,
  "total_travel_time_minutes": 29.8,
  "warnings": [
    "Açılış saatleri bilinmiyor: 3 mekan için program bu kısıt dikkate alınmadan oluşturuldu."
  ],
  "created_at": "2026-08-07T12:00:00",
  "days": [
    {
      "day_index": 0,
      "stops": [
        {
          "place_id": 12, "name": "Ayasofya", "lat": 41.0086, "lng": 28.9802,
          "day_index": 0, "order_index": 0,
          "arrival_time": "09:00", "departure_time": "09:30",
          "visit_duration_minutes": 30,
          "travel_time_to_next_minutes": 4.2, "travel_distance_to_next_km": 1.75
        }
      ]
    }
  ]
}
```

Errors: `400 INVALID_OPTIMIZATION_REQUEST` (empty selection, unowned place
id, bad `HH:MM`/date format, `end_time <= start_time`, `duration_days < 1`,
unknown `strategy`), `404 TRIP_NOT_FOUND`, `403 PERMISSION_DENIED` (viewer
role).

### `GET /internal/trips/{trip_id}/itineraries`

Summary list, newest first, for anyone with any access to the trip
(owner/editor/viewer). Each summary includes `days_count`/`stops_count`
(added for the iOS Itinerary History screen — see
`docs/ios-trip-optimizer.md` — computed via two grouped queries against
`TripItineraryStop`, batched per trip, not stored redundantly).

### `GET /internal/itineraries/{itinerary_id}`

Full detail (same shape as the `optimize` response), for anyone with access
to the itinerary's trip.

## Testing

```bash
cd services/core-api
pytest tests/test_optimization_strategy.py -v   # pure unit — no DB, no HTTP
pytest tests/test_trip_optimization.py -v        # integration — full API round trip
pytest tests/ -q                                  # full suite (confirms no regressions)
```

`test_optimization_strategy.py` covers the algorithm directly (`PlaceInput`
in, `OptimizationResult` out): empty input, a single place, category-based
visit duration, opening-hours clipping vs. conflict, day-splitting,
`duration_days` derivation and overflow, `start_date` → calendar dates,
and score bounds.

`test_trip_optimization.py` covers the full stack through the API client:
happy path, persistence + list/get round trip, multiple runs coexisting
(no overwrite), Trip Builder's `TripStop` staying untouched, and the
required edge cases — one place, duplicate places, multiple cities, empty
trip, unavailable opening-hours metadata — plus request validation and
permission checks (owner/editor/viewer, non-collaborator, anti-enumeration
404s matching the Trip Sharing convention).

## Future improvements

Ranked roughly by what unlocks the most value next:

1. **BFF proxy + a UI.** This milestone is backend-only by design (see
   the task's own "do not implement multiple roadmap items at once").
   Nothing in mobile-bff/web-bff or iOS/web can call this yet.
2. **"Apply itinerary to trip"** — an explicit action that copies a chosen
   `TripItinerary`'s stops into `TripStop`, so a user can generate several
   candidates and pick a winner. Currently the only such destructive write
   is Trip Builder's own `update_stop_order`.
3. **A second strategy** to prove the interface actually decouples cleanly
   — e.g. an OR-Tools-based strategy that solves opening-hours conflicts
   for real, or a Google/Apple Maps-backed strategy for real travel times.
4. **Populate `Place.category`/`Place.opening_hours`** from a real source
   (Google Places, OSM `opening_hours` tags) — until then, every itinerary
   uses the flat default visit duration and always warns about missing
   hours.
5. **Weekday/seasonal opening hours**, not just a flat daily window.
