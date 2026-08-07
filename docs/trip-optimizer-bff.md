# AI Trip Optimizer — Mobile BFF & Web BFF

Exposes core-api's [Trip Optimizer](trip-optimizer.md) through both BFFs.
Pure proxy layer — no optimization logic, no validation beyond what FastAPI's
Pydantic parsing already gives for free, no persistence. Every actual
decision (route ordering, day-splitting, scoring, warnings, access control,
ownership checks) happens exactly once, in core-api.

## Why both BFFs expose the same three endpoints

Trip Sharing's BFF split is asymmetric on purpose: web only gets the
invite-*recipient* surface (preview/accept/decline), because "web is
view/share, iOS is create/manage" was an explicit product decision (see
`docs/shared-trip-analytics.md` and the web `trip_sharing.py` docstring).

The Trip Optimizer has no such asymmetry — nothing about "generate an
itinerary" is mobile- or web-specific, and this task's own requirement is
to mirror mobile-bff's endpoints on web-bff exactly. So, unlike Trip
Sharing, **web-bff here gets the full owner/editor surface**: optimize,
list itineraries, get itinerary — identical to mobile-bff. This is the
first time web-bff talks to the `Trip` entity at all (Trip Builder itself
has always been mobile-bff-only).

## Architecture

```
services/mobile-bff/app/routes/trip_optimization.py
services/web-bff/app/routes/trip_optimization.py
```

Both files are structurally identical to their respective `trip_sharing.py`
(same repo, same pattern): parse the request into a Pydantic model that
mirrors core-api's DTO field-for-field → forward it to
`{CORE_API_URL}/internal/...` with `x-user-id` set from the decoded JWT →
on `status_code >= 400`, hand the response to `raise_from_response()` →
otherwise return `resp.json()` verbatim. Neither file imports or
duplicates anything from `app/domain/optimization` (core-api) — the BFFs
don't know the algorithm exists.

Each BFF registers the router the same way `trip_sharing.router` is
registered — `app.include_router(trip_optimization.router, prefix="/api/mobile")`
(or `/api/web`) — one line in `main.py`, no other wiring.

## Exposed routes

| Method | Mobile BFF | Web BFF | Proxies to (core-api) | Auth |
|---|---|---|---|---|
| POST | `/api/mobile/trips/{trip_id}/optimize` | `/api/web/trips/{trip_id}/optimize` | `POST /internal/trips/{trip_id}/optimize` | required (owner/editor) |
| GET | `/api/mobile/trips/{trip_id}/itineraries` | `/api/web/trips/{trip_id}/itineraries` | `GET /internal/trips/{trip_id}/itineraries` | required (owner/editor/viewer) |
| GET | `/api/mobile/itineraries/{itinerary_id}` | `/api/web/itineraries/{itinerary_id}` | `GET /internal/itineraries/{itinerary_id}` | required (owner/editor/viewer) |

"Required" means a valid `Authorization: Bearer <JWT>` — role enforcement
(owner/editor vs. viewer) happens in core-api's `OptimizationService`, not
in the BFF; the BFF only resolves *who* is asking, not *what they're
allowed to do*.

## Request/response contracts

### `POST /trips/{trip_id}/optimize`

Request body — identical field set, types, and defaults to core-api's
`OptimizeTripRequest` (`services/core-api/app/application/dto/optimization_dto.py`):

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

Only `selected_place_ids` is required; the other five default exactly as
core-api's own DTO defaults them (verified in tests — see "Differences"
below for the one place this could silently drift).

Response body: core-api's `OptimizeTripResponse`, returned unchanged
(`resp.json()`, no re-serialization, no field renaming/omission):

```json
{
  "id": 4,
  "trip_id": 1,
  "strategy_name": "greedy_distance",
  "optimization_score": 87.5,
  "total_distance_km": 12.4,
  "total_travel_time_minutes": 29.8,
  "warnings": ["Açılış saatleri bilinmiyor: 3 mekan için program bu kısıt dikkate alınmadan oluşturuldu."],
  "created_at": "2026-08-08T10:00:00",
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

### `GET /trips/{trip_id}/itineraries`

No request body. Response: core-api's `ItineraryListResponse`, unchanged —
`{"itineraries": [ItinerarySummaryResponse, ...]}`, newest first.

### `GET /itineraries/{itinerary_id}`

No request body. Response: the same `OptimizeTripResponse` shape as the
`optimize` endpoint (full detail, not the summary).

## Differences from the core API

These are the only places BFF behavior isn't a byte-for-byte mirror of
core-api's:

1. **Auth mechanism.** core-api trusts a raw `x-user-id` header (it's
   internal-only, gated by `verify_internal_secret`, never reachable from
   a browser/app directly). The BFF is the actual trust boundary: it
   decodes a real `Authorization: Bearer <JWT>`, and only *then* sets
   `x-user-id` on the outgoing internal request. A client can't set
   `x-user-id` itself — it isn't part of either BFF's public request DTO.

2. **Error envelope shape.** core-api: `{"error": {"code", "message"}}`.
   Both BFFs: flat `{"code", "message"}` (no `"error"` wrapper) — same
   flattening `trip_sharing.py` already does for every other error. The
   `message` text also changes: core-api's message is developer-facing
   Turkish; each BFF substitutes its own audience-tuned message from
   `_MOBILE_MESSAGES`/`_WEB_MESSAGES` (`error_wrapper.py`), keyed by the
   same `code`.

3. **Status code mapping isn't always 1:1, and mobile ≠ web here.**
   `TRIP_NOT_FOUND`/`ITINERARY_NOT_FOUND` → 404 and `PERMISSION_DENIED` →
   403 on both (unchanged from core-api). But a core-api
   `INTERNAL_SERVER_ERROR` (500) becomes **500 on mobile-bff** and
   **503 on web-bff** — an existing, pre-dating-this-feature asymmetry in
   each service's `_parse_core_error` (mobile treats it as a hard server
   error; web treats the whole "database/ML/internal" class as a retryable
   503, "sunucu... geçici olarak kullanılamıyor"). Not introduced by this
   feature — inherited from each BFF's existing error-mapping convention
   and confirmed by `test_optimize_propagates_upstream_internal_error*` in
   both test suites.

4. **Web-bff's endpoint surface here is broader than its own Trip Sharing
   precedent** — see "Why both BFFs expose the same three endpoints" above.
   This is a deliberate, requirement-driven departure, not an oversight.

5. **No BFF-side validation duplication.** Neither BFF re-checks
   `duration_days >= 1`, time formats, place ownership, or role
   permissions — Pydantic only validates *types* (e.g.
   `selected_place_ids` must be a list of ints), never business rules.
   Every business-rule error (`INVALID_OPTIMIZATION_REQUEST`,
   `TRIP_NOT_FOUND`, `PERMISSION_DENIED`, `ITINERARY_NOT_FOUND`) always
   originates in core-api and is only *translated*, never generated, by
   the BFF.

## Testing

```bash
cd services/mobile-bff && pytest tests/test_trip_optimization.py -v
cd services/web-bff     && pytest tests/test_trip_optimization.py -v
```

16 tests per service, in four groups (mirrors the file's own section
comments):

- **Authentication** — all three routes reject a missing token (403 on
  mobile-bff's `HTTPBearer(auto_error=True)`, 401 on web-bff's manual
  check — a pre-existing difference, not introduced here; see
  `test_trip_sharing.py`'s `test_create_share_requires_auth` for the same
  asymmetry on an existing route).
- **Unit (route/forwarding behavior)** — one happy-path test per endpoint,
  asserting the exact outgoing URL and the `x-user-id` header derived from
  the JWT.
- **Integration (DTO compatibility)** — a full custom request round-trips
  unchanged; an all-defaults request round-trips with exactly core-api's
  own defaults (this is the test that would catch the BFF's `OptimizeTripRequest`
  silently drifting out of sync with core-api's); the response body passes
  through byte-for-byte.
- **Error propagation** — `INVALID_OPTIMIZATION_REQUEST` (400),
  `TRIP_NOT_FOUND`/`ITINERARY_NOT_FOUND` (404), `PERMISSION_DENIED` (403),
  `INTERNAL_SERVER_ERROR` (500 mobile / 503 web), and an unreachable
  core-api (`httpx.ConnectError` → 503 `SERVICE_UNAVAILABLE` on both).

Full suite (confirms no regressions on existing routes):

```bash
cd services/mobile-bff && pytest tests/ -q   # 96 passed (80 pre-existing + 16 new)
cd services/web-bff     && pytest tests/ -q   # 53 passed (37 pre-existing + 16 new)
```

## What's still missing

No mobile/web UI calls these routes yet — this milestone is BFF-only, same
scope discipline as the optimizer's own backend milestone. See
`docs/trip-optimizer.md` "Future improvements" for the ranked next steps.
