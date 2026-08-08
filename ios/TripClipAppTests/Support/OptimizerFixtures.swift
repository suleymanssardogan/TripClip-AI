@testable import TripClipApp

/// Test sabitleri — docs/trip-optimizer-bff.md'deki örnek yanıtla aynı şekil.
enum OptimizerFixtures {

    static func itinerary(
        id: Int = 4,
        score: Double = 87.5,
        warnings: [String] = [],
        days: [ItineraryDay]? = nil
    ) -> Itinerary {
        Itinerary(
            id: id, tripId: 1, strategyName: "greedy_distance",
            optimizationScore: score, totalDistanceKm: 12.4, totalTravelTimeMinutes: 29.8,
            warnings: warnings, createdAt: "2026-08-08T10:00:00",
            days: days ?? [oneDayWithTwoStops]
        )
    }

    static var oneDayWithTwoStops: ItineraryDay {
        ItineraryDay(dayIndex: 0, stops: [
            ItineraryStop(
                placeId: 12, name: "Ayasofya", lat: 41.0086, lng: 28.9802,
                dayIndex: 0, orderIndex: 0,
                arrivalTime: "09:00", departureTime: "09:30", visitDurationMinutes: 30,
                travelTimeToNextMinutes: 4.2, travelDistanceToNextKm: 1.75
            ),
            ItineraryStop(
                placeId: 7, name: "Topkapı Sarayı", lat: 41.0115, lng: 28.9833,
                dayIndex: 0, orderIndex: 1,
                arrivalTime: "09:34", departureTime: "10:34", visitDurationMinutes: 60,
                travelTimeToNextMinutes: nil, travelDistanceToNextKm: nil
            ),
        ])
    }

    static var emptyDays: [ItineraryDay] { [] }

    static func summary(
        id: Int,
        score: Double = 87.5,
        createdAt: String? = "2026-08-08T10:00:00",
        warnings: [String] = [],
        daysCount: Int = 1,
        stopsCount: Int = 2
    ) -> ItinerarySummary {
        ItinerarySummary(
            id: id, tripId: 1, strategyName: "greedy_distance",
            optimizationScore: score, totalDistanceKm: 12.4, totalTravelTimeMinutes: 29.8,
            warnings: warnings, createdAt: createdAt,
            daysCount: daysCount, stopsCount: stopsCount
        )
    }
}
