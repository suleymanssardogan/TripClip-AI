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
  difference is route quality, not correctness. **Also the only choice**
  when any selected place has real opening-hours data and the caller wants
  it genuinely respected (not just clipped/warned) — see "`ortools`
  strategy → Hard opening-hours time windows." Not a factor today in
  practice (no pipeline populates `Place.opening_hours` yet), but already
  fully implemented and tested for whenever that changes.

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

### Hard opening-hours time windows — day-aware

Where `greedy_distance` only ever treats opening hours as a **soft**
signal (clip an early arrival to the opening time, warn on a late one, but
never reorder anything), `ortools` treats a place's known opening hours as
a genuinely **hard constraint on route ordering** — the route search
itself will refuse orderings that can't visit every constrained place
within its own window, and will actively reorder unconstrained places
around the constrained ones to make that possible. This hard constraint is
evaluated **day-aware**: a stop's window is checked against the real local
clock of whichever day it's actually scheduled on, not a single clock
shared by the whole trip (see "The single-continuous-timeline bug" below
for the mismatch this closes, and why).

**Model**: instead of one big multi-day solve, the route is built **one
day at a time** (`_solve_day`, driven by `_solve_day_aware_schedule`).
Each day reuses the exact same open-path model (`_solve_distance_only`'s
virtual depot with zero-cost edges) plus a `"Time"` `RoutingDimension`,
but that dimension is **fresh for every day**:

- `fix_start_cumul_to_zero=True` anchors `0` to *that day's own*
  `preferred_start_time` — not a running total carried over from
  yesterday. A hard window's bounds are translated into this day-relative
  scale (`open_minutes - day_start`, clamped to `[0, day_budget]`) — the
  exact same translation every day, since `preferred_start_time`/
  `preferred_end_time` don't vary per day (see "Assumptions").
- Each edge's transit cost is `service_time(from) + travel_time(from,
  to)` — unchanged from before.
- A place with **no** opening-hours data gets the day's full free range
  (`[0, day_budget]`) — unconstrained, free to be sequenced anywhere
  *that day*. This is requirement 3's "places without opening-hours data
  must remain optimizable."
- Every place is `AddDisjunction`-optional for the day (large penalty for
  skipping) **except on the last allowed day**, where every remaining
  place is mandatory — see "Day boundaries" below. This is what lets the
  solver itself decide "does this place fit today, or should it roll to
  tomorrow" instead of a hand-rolled retry loop.

This whole per-day model is only used **when at least one place in the
request has a valid opening-hours window** — if none do (today, the
overwhelming majority of real requests, since `Place.opening_hours` is
populated by no pipeline stage — see "Assumptions"), `ortools` falls
through to the exact same single-pass pure-distance model used before any
opening-hours work existed, with byte-identical results (confirmed: the
"Benchmark" table above is unchanged, verified by rerunning the same
script). Day-aware hard time windows are strictly additive functionality,
never a behavior change for the common case.

### The single-continuous-timeline bug (fixed this milestone)

The first hard-window implementation (previous milestone) used **one**
`"Time"` dimension for the whole trip — a clock that started at
`day_start` and only ever grew, with day-splitting happening entirely
afterward as separate post-processing. The solver's feasibility check ran
against that raw, ever-growing number; the real, displayed arrival time
(after the post-hoc walk reset the clock each day) was a different number
entirely, and the two were never cross-checked.

Mathematically, this can't manifest as a silently-missed *late* violation
(a day-reset can only ever *reduce* the walk's local time below what the
solver checked, and early arrivals get silently clipped up to the opening
time) — so the actual, verified failure mode was different and, in
practice, worse:

- **False "impossible."** Two places that both open only 09:00–09:30,
  far enough apart to force a natural multi-day split from sheer travel
  time — the correct answer is trivially "one per day, both arrive
  exactly at their own day's opening." The old solver instead saw this as
  globally infeasible (both windows competed for the same slice of one
  unbounded clock) and discarded **both** hard constraints via the
  relaxation fallback — even though a day-aware model satisfies both
  perfectly. Reproduced directly; now fixed — see
  `test_two_incompatible_same_window_places_satisfied_across_separate_days`.
- **A stale-arrival bug in that same fallback's own walk.** When the
  day-flush-and-retry loop detected overflow, it computed the
  opening-hours conflict check using the arrival value from *before* the
  flush (carried over from the previous day's end), which could wrongly
  flag a stop as conflicting even though its real, post-flush arrival was
  exactly on time. Reproduced directly — a place with a real arrival of
  09:00 inside its own 09:00–09:30 window still got a spurious
  "çakışıyor" warning. The new day-by-day walk (`_walk_day_groups`) has no
  retry loop at all — day boundaries are already decided before the walk
  runs — so this class of bug can't recur by construction.

### Why a per-day single-vehicle loop, not a multi-vehicle VRP

A "real" multi-day VRP (one OR-Tools *vehicle* per day, solved jointly,
with cross-day load-balancing) was considered and rejected. It would
require vehicle-count minimization and soft-capacity tuning across the
*whole* trip at once — meaningful extra complexity this codebase doesn't
otherwise need, since nothing here requires jointly optimizing which
places go on which day *relative to each other* — day-packing has always
been (and remains) a greedy, sequential decision: fill today, then decide
tomorrow with whatever's left.

The chosen design reuses the **exact same single-vehicle model already
built**, just invoked once per day instead of once for the whole trip,
with `AddDisjunction` (standard, well-supported OR-Tools functionality —
not multi-vehicle machinery) driving the "does this fit today" decision.
This closes the mismatch **by construction** (each day's hard-window
check is checked against that day's own real clock, not a coincidence)
while keeping the model the smallest one that's actually correct.

### Examples: constrained vs. unconstrained routes

Four places — A (west), C (middle), B (east), D (south) — where the
purely geographic optimum visits them in a sweep (`B → C → A → D`,
461.6 km). Giving **C** a narrow morning window (`09:00-09:30`) forces the
route to start there instead, since nothing else could reach C in time:

| | Order | Total distance | Notes |
|---|---|---|---|
| Unconstrained | B → C → A → D | 461.6 km | Pure nearest-structure sweep |
| C constrained to 09:00–09:30 | **C** → B → D → A | 545.5 km | +83.9 km (+18.2%) — the price of visiting C first |

This is the concrete trade-off hard time windows introduce: a route that
respects real business hours can be measurably longer than the pure
distance optimum — expected and correct, not a regression (see
`test_narrow_window_forces_reordering_relative_to_pure_distance`).

Three places with **compatible**, sequential windows (each reachable from
the previous one with margin to spare) are satisfied with zero warnings:

```
P1  09:00-10:00 window → arrives 09:00
P2  10:15-11:15 window → arrives 10:17  (17 min travel from P1)
P3  11:30-12:30 window → arrives 11:33  (16 min travel from P2)
```

**Two places both open only 09:00–09:30, ~700 km apart** — no *single day*
can reach both in time, but the day-aware model doesn't need to: it puts
one on day 0 and the other on day 1, and both arrive exactly at their own
day's 09:00 opening. Zero relaxation, zero conflict warnings:

```json
{
  "days": [
    { "day_index": 0, "stops": [{ "place_id": 2, "arrival_time": "09:00" }] },
    { "day_index": 1, "stops": [{ "place_id": 1, "arrival_time": "09:00" }] }
  ],
  "warnings": [
    "Uzak → Yakın: uzun bir seyahat segmenti (563 km)"
  ]
}
```

This is the exact scenario "The single-continuous-timeline bug" above's
false-"impossible" case used to mishandle — see
`test_two_incompatible_same_window_places_satisfied_across_separate_days`
(the milestone's "critical regression test") for the full before/after.

### Impossible routes

A hard window can still be truly unsatisfiable — not "unsatisfiable
today" (day-aware scheduling already handles that by rolling the place to
tomorrow), but unsatisfiable **no matter which day it's placed on**. Two
cases:

1. **A window that never overlaps `[day_start, day_end]` at all** — e.g.
   a place that only opens after the trip's `preferred_end_time`, every
   day, since the daily window is identical every day (see "Assumptions:
   opening hours are daily-only"). Detected up front
   (`_window_overlaps_day`) before any day is solved; that place's hard
   constraint is dropped for the whole schedule.
2. **`duration_days` caps the trip too tightly** — e.g. the two-far-apart-
   same-window example above, but with `duration_days: 1`: there's no
   second day to roll the conflicting place onto, so the *last* (mandatory)
   day's solve genuinely has no feasible assignment for both.

Per requirement 6/4 ("do not drop places... do not silently violate
opening hours... use existing relaxation/fallback"), neither case ever
produces a partial or empty result: the affected day falls back to
`_solve_distance_only` for whatever's left (identical to the no-windows
path — every remaining place still included) and the response gets an
explicit warning:

> *"Bazı mekanların açılış saatleri birbiriyle uyumsuz olduğu için sabit
> zaman kısıtları gevşetildi; rota yalnızca mesafeye göre sıralandı."*

Critically, this relaxation is now **per-day**, not global: only the
specific day (or days) that genuinely couldn't satisfy their hard windows
fall back — every other day's places keep their real, verified hard-window
guarantee. This is strictly more precise than the previous milestone's
all-or-nothing relaxation (which, per the false-"impossible" bug above,
could discard every hard constraint in the whole trip over a single
resolvable-by-day-splitting conflict).

### Overnight/edge-time windows: unsupported, degrades safely

`_parse_opening_hours` (imported from `greedy_distance_strategy.py`,
**unmodified** — this milestone's own constraint) does not correctly
handle a window that crosses midnight, e.g. `"22:00-02:00"`: it returns
`(1320, 120)` — a structurally "valid" tuple whose `open_minutes` exceeds
`close_minutes`, not a wraparound range. Handing that directly to OR-Tools'
`CumulVar.SetRange` **crashes** (confirmed empirically — the C++ solver
raises `"CP Solver fail"`), since a range with `lower > upper` is an empty,
invalid domain.

`_valid_hard_window` guards against this: any place whose parsed window
has `open_minutes > close_minutes` is treated as having **no** hard
window — same free range as a place with no opening-hours data at all,
for that one place only, on every day it's considered for (this does not
affect any other place's constraints, and does not trigger the
"impossible route" fallback). The existing soft post-processing check
still runs unchanged in `_walk_day_groups`, so the place still gets its
"çakışıyor" warning if its (day-local) arrival happens to land after the
raw, inverted `close_minutes` value — behaviorally identical to how
`greedy_distance` already (mis)handles the same input, since fixing
`_parse_opening_hours`'s wraparound support is out of this milestone's
scope too (would require modifying `greedy_distance_strategy.py`).

### Day boundaries

Every day's solve respects `preferred_start_time`/`preferred_end_time`
(via the day-relative `[0, day_budget]` dimension range) and each place's
category-based visit duration and travel time (via the transit callback)
— a place is only included on a given day if the solver can actually
prove it fits, given everything already scheduled that day. On a
**non-final** day this is enforced by `AddDisjunction`: a place that
would push the day over budget is dropped (deferred to tomorrow) rather
than silently accepted — requirement 5's "a stop must not silently spill
into another day" is a hard guarantee here, not a best-effort one (see
`test_non_final_day_never_lets_a_stop_silently_spill_past_day_end`).

**`duration_days`** caps how many of these per-day solves run: the loop
stops after `duration_days` days, and the *last* one is `mandatory=True`
— every remaining place goes there regardless of budget, matching
`greedy_distance`'s and the previous milestone's own "forced last day"
behavior (single overflow warning, nothing dropped). Without
`duration_days`, the loop keeps going (one day per iteration) until every
place is scheduled — day count is still derived, not guessed, exactly as
before.

**One deliberate, narrow exception to "never silently overflow":** a
single place whose own visit duration alone exceeds the entire day budget
(e.g. a 90-minute category visit against a 60-minute custom day budget) is
still allowed to be that day's sole stop, mirroring `greedy_distance`'s
own "a lone stop may overflow" rule (see
`test_service_duration_alone_exceeding_budget_still_scheduled_not_dropped`).
Mechanically: the OR-Tools "Time" dimension's own capacity is kept
generously larger than `day_budget` (`day_budget` + the longest possible
single visit duration), and only the dimension's `End` node — which
"absorbs" the last-visited place's own service time on the exit transit —
gets that generous range; every *real* place node keeps its normal
`[0, day_budget]` (or hard-window) bound, so this exception never lets a
*second* place sneak in past budget, only ever the lone final one.

### Performance

The per-day model reuses the exact same `SOLUTION_LIMIT`/
`TIME_LIMIT_SECONDS` search parameters as the no-windows path for *each*
day's solve — day-awareness doesn't introduce a second, unbounded search
loop, just the same bounded search repeated once per day. Benchmarked at
10/20/40 places, with and without opening-hours constraints (~1/3 of
places windowed, `preferred_start_time`/`end_time` `09:00`–`18:00`):

| Places | No windows | ~1/3 windowed | Days (no windows / windowed) |
|---|---|---|---|
| 10 | 93 ms | 83 ms | 5 / 7 |
| 20 | 164 ms | 252 ms | 10 / 11 |
| 40 | 713 ms | 605 ms | 17 / 19 |

Worst case — **every** place windowed, day budget tight enough to force
maximal day-splitting (one place per day):

| Places | Time | Days |
|---|---|---|
| 10 | 223 ms | 10 |
| 20 | 298 ms | 19 |
| 40 | 1065 ms | 39 |

Even 40 separate per-day solves (the most any of these benchmarks ever
triggers) complete in ~1 second total — `solution_limit` terminates each
individual day's search well before its `time_limit` in every case
measured, the same way it already did for the single-pass model. No
meaningful performance regression from day-awareness; the windowed
numbers are, if anything, noisy in *either* direction relative to the
unwindowed ones (more days sometimes means more, smaller, faster solves).
The full core-api suite (441 tests, including all opening-hours tests) —
runs in well under a minute.

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
  real signal in production data. When it *is* present, the two strategies
  now diverge: `greedy_distance` still only ever treats it as a soft
  clip/warning signal (unchanged), while `ortools` treats it as a hard
  ordering constraint — see "`ortools` strategy → Hard opening-hours time
  windows."
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

- **`greedy_distance` never re-shuffles for opening-hours conflicts.** If a
  stop's computed arrival lands after closing, it warns but keeps the stop
  where the greedy walk put it — never tries a different day or position.
  Unchanged, since `greedy_distance_strategy.py` was not modified.
- **`ortools` respects known opening hours as a day-aware hard
  constraint** — each day's hard-window check runs against that day's own
  real local clock, not a single trip-wide timeline (see "`ortools`
  strategy → Hard opening-hours time windows — day-aware"). The previous
  milestone's "single continuous timeline" caveat — where a constrained
  place's solved feasibility could disagree with its real, post-day-split
  arrival — is fixed, not just documented; see "`ortools` strategy → The
  single-continuous-timeline bug" for the two concrete failure modes this
  closes, both reproduced and covered by regression tests.
- **Day-packing is still greedy and sequential (fill today, then decide
  tomorrow), not a jointly-optimized multi-day model.** Each day's solve
  only sees "everything not yet scheduled," never looks ahead to how
  today's choices affect tomorrow's options. This is a deliberate scope
  choice, not an oversight — see "`ortools` strategy → Why a per-day
  single-vehicle loop, not a multi-vehicle VRP." In practice this only
  matters for route *quality* (a jointly-optimized assignment could
  occasionally find a shorter total route), never for correctness — every
  day's hard windows are still genuinely, individually verified.
- **Mutually incompatible hard windows fall back to distance-only
  ordering, with a warning** — `ortools` never fails the request or returns
  an incomplete itinerary; see "`ortools` strategy → Impossible routes."
- **Overnight/midnight-crossing opening-hours windows aren't correctly
  parsed by either strategy** (`_parse_opening_hours`, shared,
  unmodified) — `ortools` additionally guards against this crashing the
  solver (see "`ortools` strategy → Overnight/edge-time windows"), but
  doesn't fix the underlying parsing; both strategies' behavior for such
  input is unchanged from before this milestone.
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
- **A single place whose own visit duration alone exceeds the day budget
  is still allowed to overflow as that day's sole stop** (mirroring
  `greedy_distance`'s identical rule) — see "`ortools` strategy → Day
  boundaries" for the precise, narrow mechanism this uses.
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

`test_ortools_strategy.py` (45 tests) mirrors `test_optimization_strategy.py`'s
structure for `ortools`, in three layers:

- **v1 edge cases** (19 tests, unchanged since `ortools`'s own first
  milestone): 0/1/2 places, duplicate places, multiple cities, impossible
  day budgets, identical/degenerate coordinates, missing opening hours,
  multi-day splitting, a 60-place set completing quickly, and two
  determinism tests.
- **Single-pass hard-window tests** (12 tests, from the hard-opening-hours
  milestone, still passing byte-identical): a place open all day, a narrow
  window forcing a measurably costlier reorder vs. pure distance (the
  461.6→545.5 km example in "`ortools` strategy → Examples"), compatible
  sequential windows, unconstrained places staying freely optimizable
  alongside a constrained one, overnight/edge-time no-crash checks, a
  40-place set with scattered windows, an infeasibility-detected-quickly
  timing check, and score-formula preservation. Two of this layer's
  original tests were **updated** this milestone (not just kept) — see
  next bullet.
- **Day-aware tests** (14 tests, new this milestone): the critical
  regression test
  (`test_two_incompatible_same_window_places_satisfied_across_separate_days`
  — requirement 8, the exact false-"impossible" scenario from "The
  single-continuous-timeline bug," now correctly resolved across two
  days with zero relaxation); a constrained stop landing on day 1 and a
  separate one landing on day 2, each checked against that day's own
  local clock; the same opening-hours window repeated across four
  separate days; compatible windows at different times spread across
  several days; travel-to-next still computed across a day boundary; a
  visit duration alone exceeding the day budget (still scheduled, not
  dropped); a non-final day never letting a second stop silently spill
  past `day_end`; a genuinely impossible multi-day schedule (`duration_days:
  1` on the critical-regression scenario) still relaxing gracefully with a
  warning; missing opening hours staying freely optimizable in a
  multi-day trip; and two determinism tests (a general multi-day scenario,
  and the critical-regression scenario itself, both across 5 repeated
  runs). The two tests this layer **replaced** — which had asserted the
  *old, buggy* "globally impossible, relax everything" outcome for the
  two-far-apart-same-window scenario — are gone; asserting that outcome
  today would itself be a regression.

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

**441 tests total in the full suite (was 429 before this milestone; +14
net new day-aware tests in `test_ortools_strategy.py`, 2 old tests
replaced), zero regressions** — `test_optimization_strategy.py`
(`greedy_distance`, untouched), `test_strategy_comparison.py`, and
`test_trip_optimization.py` all pass completely unchanged. Full suite:
45.9s.

## Future improvements

Ranked roughly by what unlocks the most value next:

1. **Jointly-optimized (not greedy) multi-day assignment** — the current
   per-day loop is greedy/sequential: each day only sees what's left after
   the previous day, never looking ahead. A true joint optimization (still
   without needing multi-vehicle machinery — e.g. iterative re-balancing
   between adjacent days after the initial greedy pass) could occasionally
   find a shorter total route. Correctness is already solved (every day's
   hard windows are genuinely verified); this would only be a route-quality
   refinement — see "`ortools` strategy → Why a per-day single-vehicle
   loop, not a multi-vehicle VRP."
2. **Fix `_parse_opening_hours`'s overnight/midnight-crossing support** —
   would need to touch `greedy_distance_strategy.py` (explicitly out of
   scope for this and both previous OR-Tools milestones), benefiting both
   strategies at once.
3. **A Google/Apple Maps-backed strategy** for real travel times (driving/
   walking/transit) instead of flat haversine-over-25km/h — a third
   `RouteOptimizationStrategy`, same zero-API-change extension path
   `ortools` just proved.
4. **Populate `Place.category`/`Place.opening_hours`** from a real source
   (Google Places, OSM `opening_hours` tags) — until then, every itinerary
   from either strategy uses the flat default visit duration and always
   warns about missing hours, and `ortools`'s hard-window machinery, while
   fully implemented and tested, has no real production data to act on yet.
5. **Weekday/seasonal opening hours**, not just a flat daily window.
6. **Apply history** — `Trip.applied_itinerary_id` only tracks the most
   recent apply; a full log of every apply (who, when, which itinerary,
   which strategy) would need a separate table, not attempted here since
   nothing yet needs more than "what's currently applied."
