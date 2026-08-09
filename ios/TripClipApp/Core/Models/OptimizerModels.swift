import Foundation

// MARK: - AI Trip Optimizer — bkz. docs/trip-optimizer-bff.md
//
// Alan adları core-api'nin OptimizeTripResponse'uyla birebir eşleşir
// (APIClient'ın .convertFromSnakeCase decoder'ı trip_id → tripId, place_id →
// placeId gibi otomatik dönüştürür — TripModels.swift ile aynı desen).

struct Itinerary: Decodable, Identifiable, Hashable {
    let id:                     Int
    let tripId:                 Int
    let strategyName:           String
    let optimizationScore:      Double
    let totalDistanceKm:        Double
    let totalTravelTimeMinutes: Double
    let warnings:               [String]
    let createdAt:              String?
    let days:                   [ItineraryDay]

    var formattedCreatedAt: String {
        guard let raw = createdAt, let date = APIDate.parse(raw) else { return "" }
        return APIDate.displayString(from: date)
    }
}

struct ItineraryDay: Decodable, Identifiable, Hashable {
    let dayIndex: Int
    let stops:    [ItineraryStop]

    var id: Int { dayIndex }
}

struct ItineraryStop: Decodable, Identifiable, Hashable {
    /// Nullable: kaynak Place silinmişse core-api null döner (ondelete=SET NULL,
    /// bkz. TripItineraryStop.place_id) — geçmiş bir itinerary satırı bu durumda
    /// bile kaybolmaz, yalnızca hangi Place'e ait olduğu bilgisi kaybolur.
    let placeId:                  Int?
    let name:                     String
    let lat:                      Double?
    let lng:                      Double?
    let dayIndex:                 Int
    let orderIndex:                Int
    let arrivalTime:              String?    // "HH:MM"
    let departureTime:            String?    // "HH:MM"
    let visitDurationMinutes:     Int
    let travelTimeToNextMinutes:  Double?
    let travelDistanceToNextKm:   Double?

    /// placeId silinmiş bir mekan için nil olabileceğinden liste kimliği
    /// gün+sıra pozisyonuna düşer (TripStop.placeId'nin aksine her zaman
    /// kalıcı bir kimlik garantisi yok).
    var id: String { "\(dayIndex)-\(orderIndex)-\(placeId.map(String.init) ?? "deleted")" }
}

struct ItinerarySummary: Decodable, Identifiable, Hashable {
    let id:                     Int
    let tripId:                 Int
    let strategyName:           String
    let optimizationScore:      Double
    let totalDistanceKm:        Double
    let totalTravelTimeMinutes: Double
    let warnings:               [String]
    let createdAt:              String?
    let daysCount:              Int
    let stopsCount:             Int

    var formattedCreatedAt: String {
        guard let raw = createdAt, let date = APIDate.parse(raw) else { return "" }
        return APIDate.displayString(from: date)
    }
}

struct ItineraryListResponse: Decodable {
    let itineraries: [ItinerarySummary]
}

// MARK: - Apply to Trip — bkz. docs/trip-optimizer.md "Apply semantics"
//
// mobile-bff /itineraries/{id}/apply route'u trip_optimization.py'nin diğer
// route'ları gibi ham pass-through (trip_transformer YOK), bu yüzden alan
// adları core-api'nin ApplyItineraryResponse/TripStopDTO'suyla birebir
// eşleşir — TripStop'un latitude/longitude'u değil, ItineraryStop'un
// lat/lng kuralı geçerli.

struct AppliedTripStop: Decodable, Identifiable, Hashable {
    let placeId:    Int
    let name:       String
    let lat:        Double
    let lng:        Double
    let city:       String?
    let category:   String?
    let dayIndex:   Int
    let orderIndex: Int

    var id: String { "\(dayIndex)-\(orderIndex)-\(placeId)" }
}

struct ApplyItineraryResult: Decodable {
    let tripId:      Int
    let itineraryId: Int
    let stops:       [AppliedTripStop]
    let stopsCount:  Int
    let appliedAt:   String?
}
