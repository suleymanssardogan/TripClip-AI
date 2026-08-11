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
itinerary was applied *most recently* — a durable log of *every* apply (and
a safe way to undo the latest one) now also exists, as of the "Apply
History & Undo" milestone below.

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

## Apply History & Undo

`Trip.applied_itinerary_id`/`itinerary_applied_at` only ever answer "what's
applied *right now*." They can't answer "what was applied before that,"
"in what order," "what did the stops look like before this apply," or "can
I safely undo the last one." This milestone adds a durable log —
`trip_itinerary_apply_history` — and a safe, transactional `undo` operation
built on top of it.

### Data model

```python
class TripItineraryApplyHistory(Base):
    __tablename__ = "trip_itinerary_apply_history"

    id                     = Column(Integer, primary_key=True)
    trip_id                = Column(Integer, ForeignKey("trips.id", ondelete="CASCADE"), nullable=False)
    itinerary_id           = Column(Integer, ForeignKey("trip_itineraries.id", ondelete="SET NULL"), nullable=True)
    previous_itinerary_id  = Column(Integer, ForeignKey("trip_itineraries.id", ondelete="SET NULL"), nullable=True)
    previous_stops         = Column(JSON, nullable=False)
    is_undo                = Column(Boolean, nullable=False, default=False)
    actor_user_id          = Column(Integer, ForeignKey("users.id"), nullable=False)
    applied_at             = Column(DateTime, default=datetime.utcnow)
```

Each row represents **one successful mutation of `TripStop`** — either a
normal apply (`is_undo=False`) or an undo (`is_undo=True`). Both are
modeled *identically*, deliberately: neither is a special case of the
other. Every row captures, from the instant immediately **before** its own
mutation:

- `previous_stops` — the complete `TripStop` snapshot (`place_id`/
  `day_index`/`order_index` — `TripStop`'s own columns; `id`/`trip_id` are
  regenerated on restore, exactly like `apply_itinerary`'s existing
  delete-and-reinsert already does). Not just place IDs — inspected the
  actual `TripStop` model before designing this; there is nothing else on
  it to lose.
- `previous_itinerary_id` — what `Trip.applied_itinerary_id` was at that
  instant. This is what an undo of *this* row restores as provenance.

And, describing the mutation's own result:

- `itinerary_id` — what `Trip.applied_itinerary_id` becomes as a result of
  this row (the applied itinerary, for a normal apply; `previous_itinerary_id`
  carried forward, for an undo).
- `actor_user_id`, `applied_at`.

### Why this symmetry matters: undo-of-undo is a natural redo

Because an undo row is captured with exactly the same shape as an apply
row (its own `previous_stops`/`previous_itinerary_id`, taken right before
*its* mutation), the row an undo produces is itself a normal, undoable
history entry under the same "latest only" rule below. Undoing an undo
therefore restores the state from before the undo — i.e. a **redo** —
without any special-casing. This wasn't a requirement handed down; it fell
out of keeping the model uniform, and is treated as a deliberate, useful
consequence rather than an accident.

### First-apply behavior: no synthetic history

`create_trip` already populates `TripStop` from the trip's initial
`place_ids` at creation time (confirmed by inspection before writing any
of this — see `test_apply_itinerary_happy_path_replaces_trip_stops`'s own
`# create_trip zaten TripStop'ları doldurdu` comment). A trip therefore
never has "no previous state," even on its very first apply — `previous_stops`
is **never** nullable and never synthetic/fake. What *is* different about
a first apply is `previous_itinerary_id`: it's `None`, because no
itinerary had been applied yet. That's the only special case, and it isn't
special-cased in code — it falls out of reading `trip.applied_itinerary_id`
(which starts `None`) at snapshot time, same as any other apply.

### Latest-only safety rule (critical)

Only a trip's single most recent apply-history row (by `id`) may be
undone. Concretely: Apply A, Apply B, then attempting to undo A's row is
rejected — `409 STALE_UNDO`, `TripStop` left completely untouched. Without
this rule, undoing A would silently overwrite whatever B changed, since
A's `previous_stops` predates B entirely. The check itself is a single
query (`MAX(id)` for the trip) compared against the requested row's `id`
— no timestamp-ordering ambiguity, no race beyond what the row's own
auto-increment `id` already resolves.

### Undo transaction

1. Resolve access (`owner`/`editor` — same convention as `apply`, not the
   stricter one used by `DELETE /internal/itineraries/{id}` — see "Why
   undo doesn't reuse delete's anti-enumeration rule" below).
2. Look up the requested history row, scoped to `trip_id` (a row
   referencing a *different* trip is `404`, not `409` — it isn't stale,
   it never applied to this trip at all).
3. Reject with `409 STALE_UNDO` unless it's the trip's latest row.
4. Re-validate every `place_id` in `previous_stops` still resolves to a
   live `Place` — the exact same defensive JOIN-based check
   `apply_itinerary` already used (a raw FK column can't be trusted; see
   "Safety" above), reused here rather than re-derived, because `TripStop.place_id`
   has no `ondelete` action of its own and a place referenced by an old
   snapshot could in principle have been removed since.
5. Snapshot the *current* `TripStop` state (what's about to be replaced)
   and the current `applied_itinerary_id` — these become the new row's
   own `previous_stops`/`previous_itinerary_id`.
6. Delete-and-reinsert `TripStop` from the target row's `previous_stops`.
   Set `Trip.applied_itinerary_id`/`itinerary_applied_at` from the target
   row's `previous_itinerary_id` — `itinerary_applied_at` is set to `None`
   whenever the restored provenance is `None` (the pair is always
   meaningful together, never one set without the other — no guessing).
7. Insert the new `is_undo=True` history row.
8. Single `commit()`.
9. Best-effort `shared_trip_itinerary_apply_undone` analytics event.

All validation (steps 1–4) happens before any write, identically to
`apply_itinerary`'s own atomicity shape — a rejected undo (stale, invalid
places, no permission) leaves `TripStop` and every history row completely
untouched.

**The saved `TripItinerary` is never written to by undo** — same
invariant `apply_itinerary` already guarantees; undo only ever reads a
`TripItineraryApplyHistory` row and writes `TripStop`/`Trip`/a new history
row.

### Why undo doesn't reuse delete's anti-enumeration rule

`DELETE /internal/itineraries/{id}` deliberately collapses "doesn't exist"
and "exists but you're a viewer" into the same `404` (see "Delete Saved
Itinerary" above) — a one-off, stricter rule scoped to that destructive
operation. Undo is conceptually a variant of *apply* (it performs the same
kind of `TripStop` replace, through the same permission gate), so it
follows `apply_itinerary`'s existing convention instead: a viewer gets
`403 PERMISSION_DENIED`, a true outsider (or nonexistent trip) gets `404
TRIP_NOT_FOUND`. Reusing delete's stricter rule here would have been
inconsistent with the operation undo actually resembles.

### Deletion semantics: history outlives the itinerary

Both `itinerary_id` and `previous_itinerary_id` are `ondelete=SET NULL`,
mirroring `Trip.applied_itinerary_id`'s own existing precedent exactly.
Deleting an itinerary (`DELETE /internal/itineraries/{id}`) **never**
removes apply-history rows that reference it — it only clears the FK on
each affected row. A `GET` of the history afterward still shows the entry,
with `itinerary_id: null`; the iOS/BFF layer renders this as "Silinmiş
optimizasyon" (see `docs/ios-trip-optimizer.md`). This was verified to
require an explicit fix: `delete_itinerary`'s existing SQLite-safe
explicit-cleanup pattern (already used for `Trip.applied_itinerary_id`,
since SQLite doesn't enforce `ON DELETE` actions without `PRAGMA foreign_keys=ON`)
had to be extended to *also* clear `TripItineraryApplyHistory.itinerary_id`/
`previous_itinerary_id` — a real bug caught by
`test_delete_itinerary_does_not_destroy_apply_history` on the very first
test run, fixed the same way `apply_itinerary`'s own FK-enforcement gap
was fixed originally (see `SqlTripRepository.delete_trip`'s identical
comment).

Deleting a *trip* cascades its apply-history rows away entirely
(`ondelete=CASCADE` on `trip_id`) — a trip's history has no meaning once
the trip itself is gone, unlike an itinerary's history entries, which
remain meaningful as long as the *trip* still exists.

### Retrieval: one query, no N+1

`GET /internal/trips/{trip_id}/itinerary-apply-history` issues a single
query — `TripItineraryApplyHistory` LEFT JOINed to `TripItinerary` (for
`itinerary_created_at`, `None` if the itinerary was deleted or the row
never had one), ordered `id DESC`. `is_undoable` is computed once in
Python from the already-fetched first row's `id`, not via a second query
per row.

### Analytics

`shared_trip_itinerary_apply_undone` (`kind="trip"`) — fired from inside
`undo_apply_history`, for the exact same reason `shared_trip_itinerary_applied`
exists and is server-only: no existing event fits an undo (it's the
inverse of `ITINERARY_APPLIED`, not a reinterpretation of it), and it's a
server-driven mutation result a client can't be trusted to report itself.
**Not** in `CLIENT_FIREABLE_EVENTS`. Payload mirrors apply's:
`trip_id`, `user_id` (whoever triggered the undo), `kind="trip"`,
`metadata={"undone_history_id", "new_history_id", "restored_itinerary_id"}`.

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

### Overnight time ranges — hard-constrained, not skipped

**Resolved as of the Overnight Time Ranges milestone.** Both a place's
`opening_hours` and the request's own `preferred_start_time`/
`preferred_end_time` planning window can now cross midnight (`"22:00-02:00"`,
`"18:00"→"01:00"`) and are handled as genuine, correctly-oriented
constraints rather than being rejected or silently mishandled — see the
new "## Overnight Time Ranges" section below for the complete design
(continuous-timeline representation, planning-day semantics, and how both
strategies stay consistent). This section is kept, renamed, for the
historical context of *why* the fix mattered:

`_parse_opening_hours` (imported from `greedy_distance_strategy.py`) does
not itself reject a window that crosses midnight — `"22:00-02:00"` parses
to `(1320, 120)`, a structurally valid tuple whose `open_minutes` simply
exceeds `close_minutes`. Historically, handing that raw pair directly to
OR-Tools' `CumulVar.SetRange` would **crash** (confirmed empirically at
the time — the C++ solver raised `"CP Solver fail"`, since a range with
`lower > upper` is an empty, invalid domain). The now-shared
`_day_relative_window` helper (`greedy_distance_strategy.py`, imported by
`ortools_strategy.py`) closes this permanently at the source: it always
produces a `(rel_open, rel_close)` pair with `rel_close >= rel_open`,
extending the closing minute by a full day (`+MINUTES_PER_DAY`) whenever
the raw pair is inverted — so an invalid `SetRange` call is now
structurally impossible, not just guarded against by skipping the
constraint.

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
- ~~**Overnight/midnight-crossing opening-hours windows aren't correctly
  parsed by either strategy.**~~ **Resolved by the Overnight Time Ranges
  milestone** — see "## Overnight Time Ranges" below. Both a place's
  `opening_hours` and the request's own planning window can now cross
  midnight and are handled correctly, consistently, by both strategies.
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
      "date": "2026-09-01",
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

`days[].date` is each day's calendar date (`"YYYY-MM-DD"`) **only when**
`start_date` was given in the request — `null` otherwise (see "Trip
Planning Date" below). This is not a new computation: both strategies
already derived this value internally (`OptimizedDay.date`) since the
optimizer's very first milestone; this field only started being *returned*
in the response.

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
to the itinerary's trip — including `days[].date`, re-derived from the
itinerary's own persisted `start_date` every time this endpoint is called
(see "Trip Planning Date" below), not just on the run that created it.

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

### `DELETE /internal/itineraries/{itinerary_id}`

Permanently deletes a saved itinerary and its `TripItineraryStop` rows.
Requires `x-user-id` header (owner or editor of the itinerary's trip). No
request body.

```json
{ "success": true }
```

**Anti-enumeration — stricter than `apply`.** `apply_itinerary` reveals a
403/404 distinction (a viewer gets `PERMISSION_DENIED`, an outsider gets
`ITINERARY_NOT_FOUND`), which lets a caller infer an itinerary exists even
without access to it. `delete` deliberately collapses both cases into the
same `404 ITINERARY_NOT_FOUND` — a viewer (or anyone else without
owner/editor access) gets the identical response a nonexistent itinerary
ID would produce. This is a one-off, intentional divergence from the
`apply`/`get`/`list` convention, scoped to delete specifically because
deletion is destructive and the milestone that added it required this
exact anti-enumeration guarantee.

**What gets deleted, and what never does:**

- `TripItinerary` (the row itself) and its `TripItineraryStop` children —
  deleted explicitly in application code, not left to the database's own
  `ON DELETE CASCADE` (see "Why explicit deletion, not just the DB's FK
  actions" below).
- `TripStop` (the trip's canonical, currently-active stop list) — **never
  touched**. An itinerary is a historical snapshot/preview, not the
  source of truth for a trip's stops (see "Architecture" above); deleting
  one has no bearing on what the trip's stops currently are, even if that
  itinerary was previously applied.
- `Place` rows — **never touched**. Deleting an itinerary only removes the
  itinerary's own references to places (`TripItineraryStop.place_id`), not
  the places themselves.
- Other itineraries belonging to the same trip — **never touched**, each
  `TripItinerary` row is independent.

**Applied-itinerary reference.** If `Trip.applied_itinerary_id` currently
points at the itinerary being deleted, it's set back to `NULL` (along with
`itinerary_applied_at`) in the same transaction — never left dangling. If
a *different* itinerary is currently applied, deleting some other
itinerary has no effect on that reference. This mirrors exactly what
`Trip.applied_itinerary_id`'s own `ON DELETE SET NULL` foreign key was
already declared for (see its model doc comment — "if the itinerary later
gains a deletable feature, the Trip shouldn't be affected by it, only lose
its 'last applied' pointer" was written in anticipation of this exact
milestone).

**Why explicit deletion, not just the DB's FK actions.** Both
`trip_itinerary_stops.itinerary_id` (`ON DELETE CASCADE`) and
`trips.applied_itinerary_id` (`ON DELETE SET NULL`) already declare the
correct cascade behavior at the schema level (see the original
`add_trip_optimizer`/`add_trip_applied_itinerary` migrations) — so in a
real Postgres deployment, a bare `db.delete(itinerary); db.commit()` would
technically produce the correct result on its own. But this project's test
suite runs against SQLite, which does not enforce `ON DELETE` actions
without an explicit `PRAGMA foreign_keys=ON` this codebase doesn't set —
`SqlOptimizationRepository.delete_itinerary` therefore deletes the child
stop rows and clears the applied-itinerary reference explicitly, in
application code, exactly mirroring the existing precedent
`SqlTripRepository.delete_trip` already established for trip deletion (see
that method's own identical comment). This makes the behavior correct and
identical in both environments rather than silently relying on
environment-specific DB enforcement.

**No migration was needed.** Both FK actions this endpoint relies on
already existed in the schema before this milestone — added specifically
in anticipation of a future delete feature (see the `applied_itinerary_id`
column's own doc comment, written well before this milestone).

Errors: `404 ITINERARY_NOT_FOUND` (nonexistent itinerary, or no owner/editor
access — see anti-enumeration above), `401 UNAUTHORIZED`.

### `GET /internal/trips/{trip_id}/itinerary-apply-history`

Requires `x-user-id` header — any resolved access (`owner`/`editor`/`viewer`)
may read, same convention as `GET /internal/trips/{trip_id}/itineraries`
(this is a read, not a mutation). Newest-first.

```json
{
  "entries": [
    {
      "id": 3, "itinerary_id": null, "itinerary_created_at": null,
      "is_undo": true, "applied_at": "2026-08-10T10:05:00",
      "actor_user_id": 1, "is_undoable": true
    },
    {
      "id": 2, "itinerary_id": 5, "itinerary_created_at": "2026-08-10T09:50:00",
      "is_undo": false, "applied_at": "2026-08-10T10:00:00",
      "actor_user_id": 1, "is_undoable": false
    }
  ]
}
```

`itinerary_id`/`itinerary_created_at` are both `null` when the row's
result isn't itinerary-derived (an undo that restored a manually-set
state) **or** when the referenced itinerary was later deleted — the API
doesn't distinguish these two cases in this field; see "Apply History &
Undo → Deletion semantics" above for why that's safe (both are correctly
represented as "no itinerary to point to"). `is_undoable` reflects the
"latest-only" rule directly — only ever `true` for at most one entry.

Errors: `404 TRIP_NOT_FOUND`, `401 UNAUTHORIZED`.

### `POST /internal/trips/{trip_id}/itinerary-apply-history/{history_id}/undo`

Requires `x-user-id` header (owner or editor). No request body. `POST`,
not `DELETE` — undo is an *action* that mutates `TripStop`, not a deletion
of the history record itself (the record survives, and becomes non-
undoable once superseded by the new row this endpoint creates).

```json
{
  "trip_id": 1,
  "history_id": 4,
  "itinerary_id": 5,
  "stops": [
    {
      "place_id": 12, "name": "Ayasofya", "lat": 41.0086, "lng": 28.9802,
      "city": "İstanbul", "category": "tarihi",
      "day_index": 0, "order_index": 0
    }
  ],
  "stops_count": 1,
  "applied_at": "2026-08-10T10:10:00"
}
```

Same shape as `ApplyItineraryResponse`, plus `history_id` (the *new* row
this undo created — useful for a client that wants to act on it without
an extra round trip) and an optional `itinerary_id` (the apply response's
own field is never `null` — an undo's restored provenance legitimately can
be).

Errors: `404 TRIP_NOT_FOUND`, `404 APPLY_HISTORY_NOT_FOUND` (nonexistent
row, or a row belonging to a different trip), `409 STALE_UNDO` (not the
trip's latest row — see "Latest-only safety rule" above),
`400 INVALID_OPTIMIZATION_REQUEST` (a place referenced by the snapshot
being restored no longer exists), `403 PERMISSION_DENIED`,
`401 UNAUTHORIZED`.

## Trip Planning Date

Lets the caller optionally anchor an itinerary to a real calendar date, so
"Day 1"/"Day 2" can be shown as "September 1st"/"September 2nd" instead of
bare ordinals — the iOS-facing goal (see `docs/ios-trip-optimizer.md`
"Trip Planning Date"). **No new request field, no new domain concept, no
migration** — `start_date` and its downstream derivation already existed
end-to-end (request → `OptimizationConstraints.start_date` →
`OptimizedDay.date` via `_date_for`, both strategies) since the optimizer's
very first milestone; the one thing that never happened was the API
actually *returning* that already-computed value. This section documents
what changed and, just as importantly, what didn't.

### What changed (the whole change)

1. `ItineraryDayResponse` gained `date: Optional[str] = None`.
2. `SqlOptimizationRepository.get_itinerary` now reads `start_date` back
   out of the itinerary's own persisted `TripItinerary.params` (already
   stored, for reproducibility/audit, since `optimize_trip`'s very first
   version — see `TripItinerary.params` docstring) and computes each
   day's `date` via `_date_for` — the exact same function
   `greedy_distance_strategy.py`/`ortools_strategy.py` already import and
   use, imported here too rather than reimplemented. **No calendar-day
   arithmetic was written for this milestone** — `_date_for` already did
   it correctly (`date.fromisoformat(start_date) + timedelta(days=day_index)`,
   pure calendar-date math, no time-of-day/timezone component at all).

That's the entire backend change. No new column, no Alembic migration
(`params` was already a flexible JSON blob capturing this exact value on
every request), no change to `OptimizeTripRequest` (`start_date` already
existed there, `Optional[str] = None`, already validated as ISO
`"YYYY-MM-DD"` by `OptimizationService`), and **no mobile-bff or web-bff
change** — both already mirror `start_date` on the request side
field-for-field, and both return `resp.json()` unmodified on the response
side (no per-field DTO to update).

### Why this was safe to add without touching the request contract

`optimize_trip`'s own flow already round-trips through the repository
before returning a response — it calls `save_itinerary` (persisting
`params`, including `start_date` if given) and then immediately
`get_itinerary` (reconstructing the response purely from persisted rows)
rather than serializing the in-memory `OptimizationResult` directly. That
existing architectural choice is what made this a **repository-only**
change: fixing `get_itinerary` to read `date` back out fixes it
identically for a fresh `.optimize` call *and* for every subsequent
`GET /itineraries/{id}` (history reload) — one code path, both callers,
no special-casing needed for "was this itinerary just generated or
reloaded from history."

### Backward compatibility

A request that never sends `start_date` (every request before this
milestone, and every request that continues to omit it) produces
`days[].date: null` for every day — `_date_for(None, day_index)` already
returned `None` before this milestone existed; nothing about that
fallback changed. Existing itineraries persisted before this milestone
also degrade gracefully: their `params` blob predates `date`-awareness on
the *reading* side, but if they were saved without `start_date` in the
first place (true for every itinerary ever created, since iOS never sent
it before this milestone), `params.get("start_date")` is simply absent
→ `None` → every day's `date` is `null`, identical to a fresh no-date
request.

### Timezone

**None — deliberately, matching the rest of this system.** Every
date/time field already in this domain (`preferred_start_time`,
`arrival_time`, `departure_time`, `start_date` itself) is a naive,
timezone-less string; there is no timezone concept anywhere in `Trip`,
`TripStop`, `TripItinerary`, or either strategy (see "Assumptions"
above). `start_date`/`date` follow the identical convention — a bare
calendar date with no offset, no UTC anchor, nothing to convert. Adding
timezone support here would be inventing a concept the rest of the domain
doesn't have, not extending one that already exists — explicitly out of
scope (see `docs/ios-trip-optimizer.md` "Trip Planning Date → Timezone
behavior" for the client-facing consequence of this).

### Opening hours: unaffected, and not date-specific

`Place.opening_hours` (`"HH:MM-HH:MM"`, when present at all — see
"Assumptions") is **not per-weekday, not per-date, and this milestone
does not change that.** A planning date makes each *day* of a multi-day
itinerary correspond to a real calendar date; it does **not** make a
place's opening hours vary by which calendar date happens to land on that
day. Monday's hours and the following Monday's hours are, and remain,
indistinguishable to both strategies — there is no per-date opening-hours
data to look up even if a strategy wanted to. `days[].date` is purely a
labeling/display concern layered on top of scheduling that already
happened; it plays no role in either strategy's constraint-solving.

### Testing

Three new tests in `test_trip_optimization.py` (route-level, full
API round trip — the layer that actually exercises `get_itinerary`):
without `start_date`, every day's `date` is `null` (backward
compatibility); with `start_date` and a narrow preferred-time window
forcing a two-day split, `days[0].date`/`days[1].date` land on
consecutive calendar dates, not 24-hour increments; and — the one
genuinely new code path this milestone touches — a `GET
/internal/itineraries/{id}` call made *after* the original `optimize`
response, on the same itinerary, still returns the correct `date`,
proving the value survives a real history reload, not just the
immediate response. `test_optimization_strategy.py`'s own pre-existing
`start_date → calendar dates` coverage (unchanged) already established
that `_date_for` itself is correct; these three only needed to prove the
response DTO/repository now *surface* that value.

## Overnight Time Ranges

Both a place's `opening_hours` and the request's own `preferred_start_time`/
`preferred_end_time` planning window can cross midnight — `"22:00-02:00"`,
`"18:00"` → `"01:00"` — and are now handled as first-class, correctly
constrained scheduling input by **both** strategies, rather than being
rejected at the API boundary or silently mishandled downstream.

### Semantic rule

The same rule applies uniformly to a place's opening window and to the
request's planning window:

```text
start <= end   →  same-day interval
start >  end   →  overnight interval, crossing midnight
```

`start == end` remains **invalid** for the planning window specifically —
this is the one part of the pre-existing contract this milestone
deliberately preserved rather than extended (see "Preferred planning
window" below); a place's own `opening_hours` has no equivalent
API-level rejection (it's optional, unvalidated metadata — an equal-value
window is parsed but degenerates to "never open," which the existing soft
conflict check already surfaces correctly, unrelated to this milestone).

### Preferred planning window: no new field, extended validation

`OptimizeTripRequest.preferred_start_time`/`preferred_end_time` are
unchanged — still the same two `"HH:MM"` string fields, same wire format,
no new field was added or considered (Req 15's explicit constraint).
`OptimizationService.optimize_trip`'s own validation changed by exactly
one comparison operator:

```python
# Before: preferred_end_time <= preferred_start_time  → rejected
# After:  preferred_end_time == preferred_start_time   → rejected
```

`18:00` → `01:00` (previously rejected with a 400) is now a valid ~7-hour
overnight planning window; `09:00` → `18:00` continues to work exactly as
before. Only genuinely equal values are still rejected — the error
message was updated to match (`"preferred_end_time, preferred_start_time'a
eşit olamaz."`, replacing the old "...'dan sonra olmalı." text); the
*meaning* that survived from the old contract is "these two values must
differ," not the old inequality's direction.

### Planning-day semantics: one day, not two

The most important design decision this milestone made: an overnight
planning window still describes **exactly one optimizer planning day**,
never two. For `start_date = "2026-08-10"`, `preferred_start_time = "18:00"`,
`preferred_end_time = "01:00"`:

```text
Day 1 (day_index = 0):
    starts 2026-08-10 18:00
    continues through midnight
    ends   2026-08-11 01:00
```

This is **not** two itinerary days — `ItineraryDay.date`/`day_index`
semantics are completely unchanged (`day_index` still increments once per
*optimizer* day, `date` is still `start_date + (day_index)` via the
existing, unmodified `_date_for` — see "Date representation" below). A
2-day trip with an overnight window produces exactly 2 `ItineraryDay`
entries, not 4 — the same day count as an equivalent same-day window
would, only each day's own internal timeline happens to span a midnight
boundary.

### Continuous-timeline representation

Internally (never exposed in the API — `arrival_time`/`departure_time`
remain plain `"HH:MM"` wall-clock strings, formatted via the existing,
unmodified `%`-based `_format_minutes`), every planning day is represented
on a **continuous** minute axis anchored at that day's own `day_start`,
which is allowed to exceed `1440` (`MINUTES_PER_DAY`) once the day crosses
midnight — `22:00-02:00` is represented internally as `22:00 → 26:00`
relative to a day that starts before it, never as the raw, inverted
`22:00 → 02:00` pair. This is exactly the translation Req 9 asked for, and
it lives in exactly one place: `_day_relative_window` (see "New shared
value types and helpers" below) — nothing downstream (OR-Tools'
`SetRange`, the greedy strategy's arrival/departure walk, day-boundary
flush checks) ever has to reason about midnight-wraparound itself; they
all just compare monotonically increasing minute values, some of which
happen to exceed 1440.

`MINUTES_PER_DAY = 24 * 60` is defined exactly once (`greedy_distance_strategy.py`)
and imported everywhere the concept is needed (`ortools_strategy.py`,
including inside `_format_minutes`'s own wraparound formatting) — no
second, independently-hardcoded `24 * 60` exists anywhere in either
strategy module (Req 9's explicit ask).

### New shared value types and helpers

All framework-agnostic (no SQLAlchemy/FastAPI import), living in
`greedy_distance_strategy.py` — the existing home for every
strategy-shared constant/helper (`_parse_hhmm`, `_parse_opening_hours`,
`_date_for`, category-duration table, etc.) — and imported by
`ortools_strategy.py` exactly the way those already were, so the two
strategies are structurally incapable of diverging on what an overnight
window *means* (only on how they *schedule around* one, which is allowed
— see "Cross-strategy agreement" below):

- **`PlanningTimeWindow`** — a frozen dataclass wrapping the *request's*
  planning window: `start_minutes`, `end_minutes` (always `>= start_minutes`,
  already extended past `MINUTES_PER_DAY` when overnight), `is_overnight`,
  `duration_minutes`. `PlanningTimeWindow.parse(start_raw, end_raw)`
  replaces the small, previously-duplicated try/except parsing block both
  strategies' `optimize()` used to carry independently — one shared
  constructor, one place where "equal start/end still raises" lives.
- **`_day_relative_window(open_m, close_m, day_start)`** — converts a
  place's raw `(open_minutes, close_minutes)` into a day-relative,
  always-monotonic `(rel_open, rel_close)` pair, correctly handling three
  cases: the place is already open when the day starts (clips to `0` —
  byte-for-byte the same result the pre-existing `max(0, open_m -
  day_start)` logic gave, for every input this milestone didn't change
  the meaning of); the place opens later the same day; and — new — the
  place's *today* occurrence already closed before `day_start`, in which
  case the *next* (tomorrow's) occurrence is used instead
  (`+MINUTES_PER_DAY`). This third case is what makes an early place
  window (e.g. `"00:00-04:00"`) correctly attach to *tonight's* overnight
  session rather than being (mis)read as a window that already passed.
- **`_window_overlaps_day(open_m, close_m, day_start, day_end)`** — `True`
  iff a place's window has *any* relevant occurrence within
  `[day_start, day_start + day_budget]`. Used by `ortools` to build
  `unconstrained_ids` (a window that can never be satisfied *on any day*,
  since every day repeats the same `day_start`/`day_end`, is relaxed
  up-front rather than driving the solver toward an artificial
  infeasibility).
- **`_resolve_arrival(current_time, day_start, day_end, open_m, close_m)`**
  — the shared "soft" scheduling primitive both strategies' post-processing
  walk now call (`GreedyDistanceStrategy.optimize`, `ortools_strategy.py`'s
  `_walk_day_groups` and its own no-hard-windows fallback branch): waits
  silently for opening exactly like before, still never reshuffles a
  conflicting stop (Req 3's explicit "must not accidentally convert the
  interval into a negative duration" — a conflict still just produces the
  existing warning text, at the existing point in the schedule). The one
  new behavior: if a place's window has already closed *today* but the
  *next* occurrence still fits within `day_end`, arrival shifts to that
  next occurrence instead of immediately conflicting — this is what makes
  Case C below work, and is deliberately **not** applied when the shifted
  occurrence would exceed `day_end` (Case D), so this never becomes an
  unbounded "wait for a day that never comes" loop.

### Opening-hours scheduling semantics, worked examples

Given planning window `18:00 → 01:00` (`day_start = 18:00`, effective
`day_end = 01:00` next day):

- **Case A** — place open `19:00-23:00` (same-day): fully compatible.
  Arrival waits silently until `19:00`, departs before `23:00`.
- **Case B** — place open `22:00-02:00` (overnight, same shape as the
  planning window itself): compatible. An arrival at `23:30` or `00:30` is
  valid; an arrival at `03:00` is not (past the place's own closing) —
  Req 7's exact three examples, all correctly distinguished.
- **Case C** — place open `00:00-04:00` (same-day by the place's own
  rule, but numerically early relative to an evening-starting planning
  day): `_day_relative_window`'s third case attaches this to *tonight's*
  occurrence — `00:00` (6 hours into the planning day) is a valid arrival;
  anything past the planning window's own `01:00` cutoff is not, even
  though the place itself stays open until `04:00` — the *user's own*
  preferred end time is the binding constraint, never overridden by a
  place staying open later (Req 8's explicit "the optimizer must not
  schedule visits after the user's preferred end time").
- **Case D** — planning window `09:00-18:00` (not overnight), place open
  `22:00-02:00`: `_window_overlaps_day` returns `False` — this window can
  never be satisfied on *any* day sharing this same `day_start`/`day_end`
  (opening-hours are daily-only, see "Assumptions"), so the place is
  treated exactly like one with no opening-hours data at all for hard-
  constraint purposes. No hidden extra day is invented to "make room" for
  it — Req 8's explicit "do not create a hidden second day just to
  satisfy the opening window."

### `ortools`: hard constraints, translated correctly

`_solve_day`'s `CumulVar(node).SetRange(...)` call now receives
`_day_relative_window`'s output, clipped into `[0, day_budget]` — always a
valid (`lower <= upper`) range, by construction, never the raw inverted
pair that used to crash the solver (see "`ortools` strategy → Overnight
time ranges — hard-constrained, not skipped" above for the historical
crash and the structural fix). `unconstrained_ids` (windows that overlap
no day at all) is computed the same way it always was, just against the
new, overnight-aware `_window_overlaps_day`.

### `greedy_distance`: same semantics, same soft scheduling

`GreedyDistanceStrategy.optimize` was, for the first time, actually
modified by this milestone (every prior milestone since `ortools` shipped
had explicitly left it untouched) — but only to call the new shared
`PlanningTimeWindow.parse`/`_resolve_arrival` helpers in place of its own
inline parsing/comparison logic; its own control flow (nearest-neighbor
construction, day-splitting via `flush_day()`, category-based visit
duration, scoring) is completely unchanged. It still never re-shuffles
stops for opening-hours conflicts — a conflicting arrival still just
produces a warning and keeps going, exactly as before.

### Cross-strategy agreement

Both strategies now derive `day_start`/`day_end` from the *same*
`PlanningTimeWindow.parse` call and resolve every place's availability
through the *same* `_day_relative_window`/`_window_overlaps_day`/
`_resolve_arrival` functions — they cannot interpret an overnight window
differently by construction, only *schedule around* one differently
(`ortools` may place a stop on a different day than `greedy_distance`
would, or route between stops differently — route *quality*, never window
*meaning*, is where they're allowed to diverge; see "Available strategies
→ When to prefer each"). `test_strategy_comparison.py` proves this
directly: the same overnight-windowed fixture is asserted to produce
*identical* arrival times and conflict-warning presence/absence across
both strategies, even though their route ordering is never asserted to
match.

### Timezone: still none

No timezone support was added, and none is planned as part of this
milestone — matching "Timezone" above, an overnight interval is purely a
**local planning-clock concept** (a naive minute-of-day value that
happens to be allowed to exceed 1440 internally), not a timezone-aware
datetime interval. `arrival_time`/`departure_time` remain plain `"HH:MM"`
wall-clock strings with no date or offset attached — a stop scheduled at
`"01:00"` on an overnight day carries no information, in the API response
itself, about which calendar date it actually falls on; `ItineraryDay.date`
(one value per *day*, not per *stop*) remains the only calendar-date
signal this system produces, unchanged from "Trip Planning Date."

### Performance

The continuous-timeline representation adds no new search dimension, no
new solver calls, and no change to `SOLUTION_LIMIT`/`TIME_LIMIT_SECONDS` —
it only changes which numbers get passed into the *same* `SetRange`/
comparison calls that already existed. Benchmarked at 10/20/40 places
(`ortools`, scattered opening-hours windows on ~1/3 of places):

| Places | No windows | ~1/3 same-day windowed | ~1/3 overnight windowed |
|---|---|---|---|
| 10 | 57 ms | 65 ms | 59 ms |
| 20 | 171 ms | 180 ms | 240 ms |
| 40 | 521 ms | 788 ms | 668 ms |

Worst case — **every** place overnight-windowed, an overnight planning
day with a budget tight enough to force one place per day:

| Places | Time | Days |
|---|---|---|
| 10 | 103 ms | 10 |
| 20 | 376 ms | 20 |
| 40 | 1054 ms | 40 |

No meaningful regression from overnight support — the overnight-windowed
numbers sit in the same noisy range the same-day-windowed numbers already
occupied before this milestone (see "`ortools` strategy → Performance"
above for the original, still-valid same-day benchmark). The no-window
path is untouched code-path-wise (it never calls `_day_relative_window`
at all) and its numbers are reproduced here unchanged, confirming that.

## Testing

```bash
cd services/core-api
pytest tests/test_optimization_strategy.py -v   # greedy_distance unit — no DB, no HTTP
pytest tests/test_ortools_strategy.py -v         # ortools unit — no DB, no HTTP
pytest tests/test_strategy_comparison.py -v      # both strategies, shared fixtures/invariants
pytest tests/test_trip_optimization.py -v        # integration — full API round trip
pytest tests/test_overnight_time_window.py -v    # shared PlanningTimeWindow/day-relative helpers, strategy-agnostic
pytest tests/ -q                                  # full suite (confirms no regressions)
```

`test_optimization_strategy.py` covers `greedy_distance` directly
(`PlaceInput` in, `OptimizationResult` out): empty input, a single place,
category-based visit duration, opening-hours clipping vs. conflict,
day-splitting, `duration_days` derivation and overflow, `start_date` →
calendar dates, and score bounds — plus, **new as of the Overnight Time
Ranges milestone** (22 tests total now; this was the first milestone to
actually modify `GreedyDistanceStrategy.optimize` since `ortools` shipped,
though only to call the new shared parsing/scheduling helpers, not to
change its own control flow): an overnight planning window is accepted,
not silently defaulted; an overnight place window's arrival before and
after midnight are both handled correctly; an arrival genuinely past an
overnight place's closing still warns; day-splitting still works under an
overnight planning window; and a no-opening-hours regression check
confirms none of the above changed the pre-existing default-window
behavior.

`test_ortools_strategy.py` (49 tests: 45 through the day-aware milestone,
plus 4 net-new for Overnight Time Ranges — 2 old "invalid window falls
back" tests were replaced by 2 more precisely-named ones, and the old
2-test "unsupported, must not crash" section was replaced by 5 tests
proving overnight windows are now genuinely hard-constrained, not just
non-crashing) mirrors `test_optimization_strategy.py`'s structure for
`ortools`, in four layers:

- **v1 edge cases** (19 tests, unchanged since `ortools`'s own first
  milestone): 0/1/2 places, duplicate places, multiple cities, impossible
  day budgets, identical/degenerate coordinates, missing opening hours,
  multi-day splitting, a 60-place set completing quickly, and two
  determinism tests.
- **Single-pass hard-window tests** (13 tests: 12 from the
  hard-opening-hours milestone, `test_invalid_time_window_falls_back_to_default_window`
  split into `test_equal_start_and_end_time_falls_back_to_default_window`
  (still-invalid case, renamed for accuracy) and
  `test_end_time_before_start_time_is_now_a_valid_overnight_window` (the
  new, opposite assertion for the exact same input this milestone made
  valid)): a place open all day, a narrow window forcing a measurably
  costlier reorder vs. pure distance (the 461.6→545.5 km example in
  "`ortools` strategy → Examples"), compatible sequential windows,
  unconstrained places staying freely optimizable alongside a constrained
  one, a 40-place set with scattered windows, an infeasibility-detected-
  quickly timing check, and score-formula preservation.
- **Overnight time ranges — hard-constrained, not skipped** (5 tests, new
  this milestone, replacing the 2 "unsupported, must not crash" tests from
  the day-aware milestone — see "Overnight Time Ranges" above for the full
  design): an overnight place window is genuinely hard-constrained
  (Case B); an early place window under an overnight planning day attaches
  to *tonight's* occurrence (Case C); a place window that's already closed
  even under an overnight planning day still conflicts; an overnight place
  window incompatible with a non-overnight planning day is unconstrained,
  not lost (Case D); and an overnight window mixed with a same-day hard
  window in the same request never crashes the solver.
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

`test_strategy_comparison.py` (39 tests: 35 from the `ortools` milestone,
plus 4 new for Overnight Time Ranges — see "Overnight Time Ranges →
Cross-strategy agreement" above) runs both strategies over
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
atomicity, repeated application, provenance, analytics), `strategy:
"ortools"` end-to-end (optimize → `strategy_name` persisted correctly →
coexists with a `greedy_distance` itinerary on the same trip in history →
applies to `TripStop` exactly like any other itinerary, since apply is
strategy-agnostic by construction) — and, new for Overnight Time Ranges,
`test_end_time_before_start_time_is_rejected` was split into
`test_equal_start_and_end_time_is_rejected` (the one input still actually
invalid) and `test_overnight_preferred_time_range_is_accepted` (a full
`POST /optimize` round trip proving `18:00`→`01:00` now returns `200`
with the itinerary's first stop arriving at `"18:00"`, not a `400`).

`test_overnight_time_window.py` (31 tests, new) tests the shared
`PlanningTimeWindow`/`_day_relative_window`/`_window_overlaps_day`/
`_resolve_arrival`/`_day_budget` helpers directly, independent of either
strategy — parser normal/overnight/malformed/missing/equal-window cases,
`PlanningTimeWindow.parse`'s same-day/overnight/equal/malformed cases,
`_day_budget`'s same-day/overnight-raw/overnight-already-extended
(idempotency) cases, `_day_relative_window`'s four semantic cases
(already-open, opens-later, overnight, rolls-to-tomorrow) plus a
property-style monotonicity check across eight input combinations,
`_window_overlaps_day`'s four overlap/non-overlap cases, and
`_resolve_arrival`'s full behavioral matrix (Cases A/B/C/D from
"Overnight Time Ranges" above, plus the pre-existing same-day conflict
case and the degenerate equal-window case) — this is the layer other
milestones' cross-strategy tests ultimately depend on being correct.

**490 tests total in the full suite (was 441 before this milestone; +49
net new: +6 in `test_optimization_strategy.py`, +4 net in
`test_ortools_strategy.py`, +4 in `test_strategy_comparison.py`, +2 net
in `test_trip_optimization.py`, +31 new `test_overnight_time_window.py`,
2 tests replaced in each of `test_ortools_strategy.py`/
`test_trip_optimization.py` for inputs that changed meaning), zero
regressions in anything this milestone didn't intentionally change** —
full suite: ~44s.

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
6. ~~**Apply history**~~ **Resolved** — see "Apply History & Undo" above.
7. **Apply-history retention/pruning** — `trip_itinerary_apply_history`
   grows unbounded per trip (one row per apply/undo, forever); there's no
   cap, archival, or pagination on `GET .../itinerary-apply-history` yet.
   Not a practical concern at current usage scale, but worth revisiting if
   a trip accumulates hundreds of applies.
8. **Redo as a distinct, labeled action** — undoing an undo already works
   and correctly restores the pre-undo state (see "Apply History & Undo →
   Why this symmetry matters"), but the UI doesn't yet present this as a
   dedicated "Redo" affordance — it's just "Undo" again, on what happens
   to be an undo row.
