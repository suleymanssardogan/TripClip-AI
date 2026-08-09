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
    greedy_distance_strategy.py — "greedy_distance" strategy (nearest-neighbor + day-splitting)
    ortools_strategy.py         — "ortools" strategy (OR-Tools routing solver + day-splitting)
    strategy_registry.py        — name → strategy instance, the extension point
app/infrastructure/repositories/
    sql_optimization_repository.py — SQLAlchemy implementation
app/application/
    dto/optimization_dto.py       — request/response Pydantic schemas
    services/optimization_service.py — validation, orchestration, dedup
app/api/internal/
    trip_optimization.py — POST /trips/{id}/optimize, GET .../itineraries,
                            GET /itineraries/{id}, POST /itineraries/{id}/apply
app/models/
    trip_itinerary.py, trip_itinerary_stop.py — persistence
    place.py — +opening_hours (nullable)
    trip.py  — +applied_itinerary_id (FK→trip_itineraries, ondelete=SET NULL),
               +itinerary_applied_at — provenance for "apply to trip" (see below)
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

### Why itineraries aren't written into `TripStop` — until explicitly applied

`update_stop_order` (Trip Builder) treats `TripStop` as the trip's one
canonical stop list. If `optimize_trip` also wrote to `TripStop`, every
optimizer run would silently overwrite whatever the owner/editor had
manually arranged — and there'd be no way to compare two optimizer runs
against each other or against the manual arrangement. Instead, each
`optimize_trip` call creates a new `TripItinerary` + `TripItineraryStop`
rows, standalone from `TripStop`. Running the optimizer is always a safe,
non-destructive "preview" — nothing about the Trip Builder API's behavior
changes as a side effect of generating or viewing an itinerary.

**Applying an itinerary is the one explicit, opt-in exception** — see
"Apply semantics" below. It's a deliberate, separate action the user takes
on a specific saved itinerary; it never happens automatically as a side
effect of `optimize_trip`.

## Apply semantics

`POST /internal/itineraries/{itinerary_id}/apply` copies a saved
`TripItinerary`'s stops into the Trip's canonical `TripStop` list — the
first (and still only) way an optimizer artifact intentionally mutates
Trip Builder data.

### Design decision: REPLACE, not merge or reorder

Three options were considered:

- **Replace** (chosen): delete the trip's existing `TripStop` rows, insert
  one row per itinerary stop, in the itinerary's own day/order. Exactly
  `update_stop_order`'s existing delete-and-reinsert transaction shape —
  no new mutation pattern introduced.
- **Merge**: union manual stops with itinerary stops. Rejected — `TripStop`
  carries no "source" or "locked" flag, so there's no principled way to
  decide which of two conflicting orderings for the same place wins, and
  a merge that silently drops or duplicates stops is worse than a full,
  predictable replace (e.g. what should happen to a manually-added stop
  the itinerary never considered, or a place appearing in both).
- **Reorder-only**: keep the existing stop set, only apply the itinerary's
  ordering. Rejected — an itinerary can reference a different subset of
  places than the trip's current stops (the optimizer runs against
  `selected_place_ids`, not "all current stops"), so a pure reorder can't
  express "this itinerary dropped/added a place."

Replace is lossless here because `TripStop` has no metadata beyond
`place_id`/`day_index`/`order_index` (see `TripStopDTO`) — nothing manual
exists to accidentally destroy. If `TripStop` ever grows per-stop notes or
similar, this decision would need revisiting.

### What happens, precisely

1. Validate: itinerary exists and its trip is resolvable; requester has
   `owner`/`editor` access to that trip (same `resolve_access` check as
   every other trip-mutating endpoint); every `TripItineraryStop` row still
   resolves to a live `Place` (see "Safety" below); the itinerary has at
   least one stop; no duplicate `place_id` across its stops.
2. Delete the trip's current `TripStop` rows, insert new ones from the
   itinerary's days/stops, set `Trip.applied_itinerary_id` and
   `Trip.itinerary_applied_at`.
3. Single `commit()` — see "Atomicity" below.
4. Best-effort: fire the `shared_trip_itinerary_applied` analytics event
   (see "Analytics" below) — a failure here never rolls back step 2.

**The saved `TripItinerary` itself is never touched** — applying is a read
of the itinerary and a write to the trip, never a write to the itinerary.
Reopening the same itinerary from Itinerary History after applying it
still shows the exact original result.

### Atomicity

All reads and validation happen before any write; the delete+reinsert+
provenance-update sequence shares one SQLAlchemy session and one final
`commit()` — a rejected apply (any validation failure) leaves the existing
`TripStop` rows completely untouched, never partially updated. Verified by
`test_apply_itinerary_atomic_rollback_leaves_existing_stops_untouched`.

### Repeated application

Applying the same itinerary twice (or a different itinerary after an
earlier apply) is always safe — each apply is a fresh replace, not additive.
`Trip.applied_itinerary_id`/`itinerary_applied_at` simply reflect whichever
itinerary was applied *most recently*, not a history of every apply. Full
apply history, if ever needed, would have to come from a separate log —
out of scope here (see "Future improvements").

### Optimizer provenance

`Trip.applied_itinerary_id` (nullable FK → `trip_itineraries.id`,
`ondelete=SET NULL`) + `Trip.itinerary_applied_at` are the smallest schema
addition that answers "which itinerary, if any, produced this trip's
current stops" — both `None` until the first apply. Deliberately placed on
`Trip`, not on `TripStop`: every apply replaces the *entire* stop set at
once, so per-stop provenance would be redundant (all stops from one apply
share the same source) and would wrongly couple the canonical route model
(`TripStop`) to the optimizer domain (`TripItinerary`). A single pointer on
`Trip` captures exactly the fact that exists, no more.

### Safety

| Failure | Response |
|---|---|
| Itinerary doesn't exist | `404 ITINERARY_NOT_FOUND` |
| Itinerary belongs to a trip the requester has no relationship to | `404 ITINERARY_NOT_FOUND` (anti-enumeration — not 403, same convention as Trip Sharing) |
| Requester is a viewer (not owner/editor) | `403 PERMISSION_DENIED` |
| Trip no longer exists | `404 TRIP_NOT_FOUND` |
| A referenced `Place` was deleted (`TripItineraryStop.place_id` → `NULL` via `ondelete=SET NULL`) | `400 INVALID_OPTIMIZATION_REQUEST` |
| Itinerary has zero stops | `400 INVALID_OPTIMIZATION_REQUEST` |
| Itinerary has a duplicate `place_id` across its stops | `400 INVALID_OPTIMIZATION_REQUEST` |
| Applying an already-applied itinerary again | `200` — no-op-equivalent, safe to repeat (see above) |

### Analytics

`shared_trip_itinerary_applied` (`kind="trip"`) — server-only, fired from
inside `apply_itinerary` itself, **not** in `CLIENT_FIREABLE_EVENTS`
(verified by a smoke test asserting membership is `False`). No existing
event fits: `SHARED_TRIP_INVITE_SENT`/`DECLINED`/`EXPIRED` are specific to
the collaboration/invite flow, and `SHARED_TRIP_CREATED`/`DELETED` are
`kind="video"` (video-plan lifecycle, unrelated to the optimizer). Payload:
`trip_id`, `user_id` (the applier), `kind="trip"`, and
`metadata={"itinerary_id", "stops_count"}`.

## Available strategies

Two `RouteOptimizationStrategy` implementations are registered today (see
`strategy_registry.py`):

| Name (`OptimizeTripRequest.strategy`) | Approach | Determinism | Default |
|---|---|---|---|
| `greedy_distance` | Nearest-neighbor construction | Deterministic (no search, one pass) | **Yes** |
| `ortools` | Google OR-Tools constraint-programming routing solver | Deterministic (bounded by a fixed solution count, not wall-clock time — see "`ortools` strategy → Determinism") | No — opt-in via `strategy: "ortools"` |

**Neither is an AI/LLM strategy.** Both are classical, fully deterministic
algorithms — nearest-neighbor construction and constraint-programming route
search, respectively. `ortools` specifically is Google's open-source
operations-research solver (the same library used for vehicle routing,
scheduling, and bin-packing problems industry-wide), not a language model
or any kind of learned/probabilistic system. There is no prompt, no
inference call, no non-determinism from sampling.

### Why `strategy` is a public API field, not internal configuration

`OptimizeTripRequest.strategy` already existed before this milestone (added
alongside `greedy_distance` itself, anticipating exactly this) — so adding
`ortools` required **zero API changes**, just a new registered name. The
alternative this milestone's own spec raised — server-side configuration
(an env var, say `DEFAULT_OPTIMIZATION_STRATEGY`) instead of a request
field — was considered and rejected: a string enum selecting between two
interchangeable, same-shape-output algorithms is a legitimate caller-facing
choice (like `sort=price` vs `sort=rating` on a listing endpoint), not an
internal implementation detail. It doesn't leak anything about *how*
either strategy works internally — the caller supplies a name, gets back
the identical `OptimizeTripResponse` shape either way, and everything
about routing math/day-splitting/scoring stays entirely server-side. A
config-only approach would additionally block the one caller-visible use
case that actually motivates having two strategies: letting a client (or a
future "regenerate with a different strategy" UI affordance) pick per
request, not just per deployment.

### When to prefer each

- **`greedy_distance`** (default): a single nearest-neighbor pass, no
  search — effectively instant regardless of selection size, and quality
  is already reasonable for small-to-medium selections (a handful to
  ~15-20 places). Good default because it has zero solver startup cost and
  a trivially auditable algorithm (one paragraph of code).
- **`ortools`**: worth the extra latency (milliseconds to low seconds,
  see "Benchmark" below) when route quality matters more than raw
  speed — larger selections (20+ places) or itineraries spanning multiple
  clusters/cities, where nearest-neighbor's well-known weakness (a single
  bad early greedy choice compounds) is more likely to leave a visibly
  suboptimal route. Both produce a *valid* itinerary either way — the
  difference is route quality, not correctness.

## `greedy_distance` strategy

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

## `ortools` strategy

Second `RouteOptimizationStrategy` implementation — this milestone's own
purpose was to prove the strategy abstraction is genuinely replaceable, so
it deliberately uses a real, widely-used constraint solver (Google
OR-Tools) rather than another bespoke heuristic.

### Architecture: same route-first/cluster-second split, smarter route-first

`ortools_strategy.py` mirrors `greedy_distance_strategy.py`'s own
architecture — it only replaces the **route-first** phase:

1. **Route-first (different from greedy):** instead of nearest-neighbor
   construction, an OR-Tools `RoutingModel` searches for a shorter open-path
   ordering — `PATH_CHEAPEST_ARC` first-solution construction, then
   `GUIDED_LOCAL_SEARCH` improvement (2-opt/Or-opt-class moves), bounded by
   a fixed solution count rather than wall-clock time (see "Determinism"
   below).
2. **Cluster-second (identical algorithm to greedy):** the resulting order
   is walked with the exact same day-splitting/opening-hours/timing/scoring
   control flow `greedy_distance_strategy.py` uses — re-implemented in
   `ortools_strategy.py` rather than imported (this milestone's own
   constraint was to leave `GreedyDistanceStrategy` completely unchanged),
   but built from the *same pure helpers* (`haversine_km`, HH:MM parsing/
   formatting, opening-hours parsing, the category → visit-minutes table),
   imported directly from `greedy_distance_strategy.py` — so the low-level
   math and constants can never silently drift between the two strategies,
   only the day-clustering control flow is duplicated, and that's each
   strategy's own "ordering/timing/day distribution" responsibility per
   `RouteOptimizationStrategy`'s own docstring, not orchestration.

### The open-path TSP trick

OR-Tools' `RoutingIndexManager` always expects a "depot" (start/end) node —
but there's no real depot here (a trip has no fixed starting location, and
`greedy_distance_strategy.py` doesn't have this concept either). The fix is
a standard OR-Tools pattern: add one virtual depot node (index 0, not a
real `Place`) with **zero-cost edges to and from every real place**. The
solver still has to visit every real node exactly once, but "starting" and
"ending" at the depot is free — net effect, it minimizes the sum of
consecutive real-stop distances, i.e. exactly an open-path TSP, with no
artificial "return to start" cost distorting the result.

### Determinism

`solution_limit` (a count of improving solutions found, `200` by default —
see `SOLUTION_LIMIT` in `ortools_strategy.py`) is the **primary** stopping
condition, deliberately *not* a wall-clock `time_limit` — the count of
local-search moves explored is independent of machine speed, so the same
input always produces the same output regardless of what else is running
on the machine. A generous `time_limit` (5s) exists purely as a safety net
against pathologically large inputs; for realistic trip sizes (tens of
places) `solution_limit` is reached well before it — confirmed empirically
(10 back-to-back solves of the same 15-place input were byte-identical) and
covered by `test_same_input_produces_identical_result_across_repeated_runs`
in `tests/test_ortools_strategy.py`. `GUIDED_LOCAL_SEARCH` itself uses no
randomness (unlike, say, simulated annealing) — it explores neighborhoods
in a fixed order and greedily accepts improving moves.

### Benchmark

Route length vs. `greedy_distance`'s nearest-neighbor, same random
place sets (see "Verification → Benchmark" for the exact script):

| Places | `greedy_distance` | `ortools` | Improvement | `ortools` full solve time |
|---|---|---|---|---|
| 10 | 1666.3 km | 1440.0 km | 13.6% shorter | 52.6 ms |
| 20 | 2316.5 km | 2240.3 km | 3.3% shorter | 143.7 ms |
| 30 | 3017.7 km | 2776.7 km | 8.0% shorter | 324.6 ms |
| 60 | 4352.5 km | 3877.1 km | 10.9% shorter | 1300.8 ms |

Solve time is the full `optimize()` call (routing search + day-clustering
walk), well under the 5s safety-net `time_limit` at every size tested —
`solution_limit` is what actually governs termination in practice (see
"Determinism" above). `ortools` is never *worse* than `greedy_distance` on
these samples (its first-solution phase alone starts from the same class
of construction heuristic, then improves on it) — but the spread (3–14%)
shows route quality is instance-dependent, not a fixed guarantee, which is
why "Available strategies → When to prefer each" frames this as "worth it for
larger/messier selections," not a blanket recommendation.

### What OR-Tools does *not* change vs. greedy (deliberate scope)

- **Opening-hours conflicts are still soft, not solved.** The `ortools`
  route search optimizes pure geographic distance; it does not know about
  opening hours at all — those are applied identically to greedy, as a
  post-processing clip/warning during the (shared-algorithm) day-clustering
  walk. OR-Tools *could* model opening hours as hard time windows on the
  routing dimension — deliberately not attempted here, to keep this
  milestone scoped to what was actually asked ("optimize stop ordering,
  geographic travel distance, multi-day distribution") rather than
  conflating two different concerns. Flagged as a natural v2 for `ortools`
  specifically in "Future improvements."
- **Day-splitting is still a post-processing pass, not a first-class
  OR-Tools model.** A "real" multi-day VRP (one OR-Tools vehicle per day,
  with per-day time-budget capacities) was considered and deliberately
  rejected for v1: it requires soft-capacity penalties and vehicle-count
  minimization tuning to avoid either infeasible solves or spreading a
  small selection needlessly across many days — meaningful extra
  complexity for uncertain gain, since day-splitting is fundamentally a
  scheduling concern that the existing (already-tested) day-clustering
  algorithm already handles reasonably. What OR-Tools contributes here is
  a better-ordered path *feeding into* that same clustering step — see
  "Architecture" above.

## Extension points

Adding a new strategy (Google Maps API, Apple Maps, an LLM-assisted
planner, …) requires no change to the service, DTOs, or API — `ortools`
is the second real implementation proving exactly this claim, not just a
hypothetical:

1. Implement `RouteOptimizationStrategy` (`app/domain/optimization/strategy.py`)
   — one method, `optimize(places: List[PlaceInput], constraints) -> OptimizationResult`.
2. Register it: `register_strategy(MyStrategy())` in
   `strategy_registry.py`.
3. Callers select it via `OptimizeTripRequest.strategy` (e.g.
   `"ortools"`) — `OptimizationService` resolves it by name and never
   imports a concrete strategy class itself. Zero lines changed in
   `optimization_service.py`, the DTOs, or the API route to add `ortools` —
   confirmed by `git diff` for this milestone touching only
   `ortools_strategy.py` (new file), `strategy_registry.py` (one import +
   one registration line), `requirements.txt`, and tests/docs.

A strategy backed by a real routing API (Google/Apple Maps) would naturally
improve travel time accuracy beyond both existing strategies' flat-speed
haversine assumption — see "Assumptions" below.

## Assumptions

Shared by **both** strategies (`ortools` imports these exact constants/
helpers from `greedy_distance_strategy.py` — see "`ortools` strategy →
Architecture"), except where noted:

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
  real signal in production data. Both strategies treat this identically
  (soft clip/warning, not a hard constraint) — see "`ortools` strategy →
  What OR-Tools does not change vs. greedy."
- **`selected_place_ids` are validated against the *trip owner's* Library**
  (`PlaceSave` rows for `Trip.user_id`), not the requesting collaborator's —
  matching how `Trip.create_trip` already resolves ownership. An editor can
  run the optimizer on the owner's places; they don't need their own copy
  of the same saves.
- **Only the trip owner and editor collaborators can run the optimizer**
  (`resolve_access` ∈ {owner, editor}); viewers can read persisted
  itineraries but not generate new ones — the same split as
  `update_stop_order`.

## Limitations

- **No re-shuffling for opening-hours conflicts, in either strategy.** If a
  stop's computed arrival lands after closing, both `greedy_distance` and
  `ortools` warn but keep the stop where their respective route search put
  it — neither tries a different day or position to resolve it. `ortools`
  *could* model this as a hard time-window constraint on the routing
  dimension — deliberately not attempted in this milestone, kept scoped to
  ordering/distance/day-distribution (see "`ortools` strategy → What
  OR-Tools does not change vs. greedy"). Flagged as the natural next
  OR-Tools enhancement in "Future improvements."
- **No real-world travel time, in either strategy.** No traffic, no
  walking-vs-driving distinction, no public transit — flat haversine
  distance over an assumed speed for both `greedy_distance` and `ortools`.
  A Google/Apple Maps-backed strategy (a third `RouteOptimizationStrategy`)
  is the natural fix, and would slot in the same way `ortools` did.
- **`greedy_distance`'s nearest-neighbor construction can be locally
  suboptimal** for larger selections (no 2-opt pass) — this is exactly what
  `ortools` exists to mitigate for callers who opt into it (see "Available
  strategies → When to prefer each" and the benchmark table there);
  `greedy_distance` itself is unchanged and remains the zero-latency
  default.
- **`ortools`'s day-splitting is post-processing, not a first-class
  OR-Tools model** (multi-vehicle VRP with per-day capacity) — see
  "`ortools` strategy → What OR-Tools does not change vs. greedy" for why
  this was a deliberate v1 scope decision, not an oversight.
- **The optimization score is not comparable across strategies** or
  validated against real user satisfaction — it's a same-strategy,
  same-run diagnostic, not a benchmark. (Route-length comparison across
  strategies is possible and shown in the benchmark table above — the
  0–100 *score*, specifically, is not the right tool for that comparison,
  since both strategies compute it from their own resulting route only.)
- **Apply keeps only the most recent provenance pointer**, not a full
  history of every apply — see "Apply semantics → Repeated application."

## API

All routes are internal (`verify_internal_secret`), proxied by both BFFs
the same way Trip Builder/Trip Sharing are — see `docs/trip-optimizer-bff.md`
for the full proxy contract and `docs/ios-trip-optimizer.md` for the iOS
consumer.

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
`strategy` accepts any registered name — currently `"greedy_distance"`
(default) or `"ortools"` (see "Available strategies"); an unrecognized
name is rejected with `400 INVALID_OPTIMIZATION_REQUEST` listing the valid
options (`strategy_registry.available_strategies()`), never silently
falls back to the default.

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

### `POST /internal/itineraries/{itinerary_id}/apply`

Requires `x-user-id` header (owner or editor of the itinerary's trip). No
request body. See "Apply semantics" above for the full behavior.

```json
{
  "trip_id": 1,
  "itinerary_id": 4,
  "stops": [
    {
      "place_id": 12, "name": "Ayasofya", "lat": 41.0086, "lng": 28.9802,
      "city": "İstanbul", "category": "tarihi",
      "day_index": 0, "order_index": 0
    }
  ],
  "stops_count": 3,
  "applied_at": "2026-08-08T10:05:00"
}
```

`stops` is `TripStopDTO` — the same shape `GET /trips/{trip_id}` already
returns for `days` (flattened, not day-grouped, since the caller just
applied a specific day/order and doesn't need it re-nested).

Errors: `404 ITINERARY_NOT_FOUND`, `404 TRIP_NOT_FOUND`,
`403 PERMISSION_DENIED`, `400 INVALID_OPTIMIZATION_REQUEST` (deleted place,
empty itinerary, duplicate places — see "Apply semantics → Safety").

## Testing

```bash
cd services/core-api
pytest tests/test_optimization_strategy.py -v   # greedy_distance unit — no DB, no HTTP
pytest tests/test_ortools_strategy.py -v         # ortools unit — no DB, no HTTP
pytest tests/test_strategy_comparison.py -v      # both strategies, shared fixtures/invariants
pytest tests/test_trip_optimization.py -v        # integration — full API round trip
pytest tests/ -q                                  # full suite (confirms no regressions)
```

`test_optimization_strategy.py` covers `greedy_distance` directly
(`PlaceInput` in, `OptimizationResult` out): empty input, a single place,
category-based visit duration, opening-hours clipping vs. conflict,
day-splitting, `duration_days` derivation and overflow, `start_date` →
calendar dates, and score bounds. **Unchanged by this milestone** — same
19 tests, still passing, confirming `GreedyDistanceStrategy` itself was
never touched.

`test_ortools_strategy.py` (19 tests, new) mirrors that same structure for
`ortools` — the required edge cases (0/1/2 places, duplicate places,
multiple cities, impossible day budgets, identical/degenerate coordinates,
missing opening hours, multi-day splitting, a 60-place set completing in
about a second) plus two determinism tests (5 repeated solves of the same
15-place input byte-identical; a fresh strategy instance each time still
agrees).

`test_strategy_comparison.py` (35 tests, new) runs both strategies over
the same six fixtures and asserts the shared contract without requiring
identical routes: registry sanity (both resolvable, `greedy_distance`
still `DEFAULT_STRATEGY_NAME`), `OptimizationResult`/`OptimizedStop`
field-type schema parity, no lost/duplicated places, valid contiguous
day/order indices, and score bounds — parametrized across strategy ×
fixture (`ids=lambda s: s.name` makes failures immediately attributable to
one strategy).

`test_trip_optimization.py` covers the full stack through the API client:
happy path, persistence + list/get round trip, multiple runs coexisting
(no overwrite), Trip Builder's `TripStop` staying untouched by generation,
and the required edge cases — one place, duplicate places, multiple
cities, empty trip, unavailable opening-hours metadata — plus request
validation and permission checks (owner/editor/viewer, non-collaborator,
anti-enumeration 404s matching the Trip Sharing convention), `apply_itinerary`
(happy path with `TripStop` before/after DB assertions, permissions,
atomicity, repeated application, provenance, analytics), and — new this
milestone — `strategy: "ortools"` end-to-end (optimize → `strategy_name`
persisted correctly → coexists with a `greedy_distance` itinerary on the
same trip in history → applies to `TripStop` exactly like any other
itinerary, since apply is strategy-agnostic by construction).

**415 tests total in the full suite (was 358 before this milestone; +57 —
19 + 35 + 3 new integration tests), zero regressions.**

## Future improvements

Ranked roughly by what unlocks the most value next:

1. **Hard opening-hours time windows in `ortools`** — model opening hours
   as a routing dimension with real time windows (OR-Tools supports this
   natively via `AddDimension` + `CumulVar` bounds) so the solver can
   actually resolve a conflict by reordering, instead of the current
   soft clip/warning shared with `greedy_distance`. The single biggest
   remaining gap between "OR-Tools is integrated" and "OR-Tools is used to
   its full potential" — see "`ortools` strategy → What OR-Tools does not
   change vs. greedy."
2. **A first-class multi-day VRP in `ortools`** (one vehicle per day,
   soft per-day time-budget capacities) instead of the current
   route-then-cluster post-processing split — would let day assignment and
   route order be optimized jointly rather than sequentially. Considered
   and deliberately deferred this milestone (see "`ortools` strategy → What
   OR-Tools does not change vs. greedy") since it requires vehicle-count
   minimization tuning to avoid regressions on the "derives day count"
   behavior already tested for both strategies.
3. **A Google/Apple Maps-backed strategy** for real travel times (driving/
   walking/transit) instead of flat haversine-over-25km/h — a third
   `RouteOptimizationStrategy`, same zero-API-change extension path
   `ortools` just proved.
4. **Populate `Place.category`/`Place.opening_hours`** from a real source
   (Google Places, OSM `opening_hours` tags) — until then, every itinerary
   from either strategy uses the flat default visit duration and always
   warns about missing hours.
5. **Weekday/seasonal opening hours**, not just a flat daily window.
6. **Apply history** — `Trip.applied_itinerary_id` only tracks the most
   recent apply; a full log of every apply (who, when, which itinerary,
   which strategy) would need a separate table, not attempted here since
   nothing yet needs more than "what's currently applied."
