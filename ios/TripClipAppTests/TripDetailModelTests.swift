import XCTest
@testable import TripClipApp

/// `TripDetail`'in `applied_itinerary_id`/`itinerary_applied_at` alanlarını
/// dekode etmesi — backend bunları HER ZAMAN gönderiyordu, model şimdiye
/// kadar bu alanları hiç TANIMLAMIYORDU (Req 8 "apply-state awareness",
/// Milestone 25). Saf model-decode testi — ağ yok, ViewModel yok
/// (`OptimizerEndpointTests`'le AYNI stil).
final class TripDetailModelTests: XCTestCase {

    private func decode(_ json: String) throws -> TripDetail {
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        return try decoder.decode(TripDetail.self, from: Data(json.utf8))
    }

    func test_decodesAppliedItineraryFields_whenPresent() throws {
        let trip = try decode("""
        {
          "id": 2, "title": "Gaziantep Gezisi", "total_distance_km": 12.4,
          "created_at": "2026-08-08T10:00:00", "stops_count": 2,
          "days": [], "applied_itinerary_id": 4,
          "itinerary_applied_at": "2026-08-08T10:05:00"
        }
        """)

        XCTAssertEqual(trip.appliedItineraryId, 4)
        XCTAssertEqual(trip.itineraryAppliedAt, "2026-08-08T10:05:00")
        XCTAssertFalse(trip.formattedItineraryAppliedAt.isEmpty)
    }

    func test_appliedItineraryFieldsDefaultToNil_whenNeverApplied() throws {
        let trip = try decode("""
        {
          "id": 1, "title": "İstanbul Gezisi", "total_distance_km": null,
          "created_at": null, "stops_count": 0, "days": [],
          "applied_itinerary_id": null, "itinerary_applied_at": null
        }
        """)

        XCTAssertNil(trip.appliedItineraryId)
        XCTAssertNil(trip.itineraryAppliedAt)
        XCTAssertEqual(trip.formattedItineraryAppliedAt, "")
    }

    func test_multiDayTrip_daysArrayPreservesDayBoundaries() throws {
        // Apply, günleri gerçek day_index sınırlarıyla trip_stops'a geri
        // yazabilir (bkz. docs/trip-optimizer.md "Apply semantics") — model
        // bunu zaten `[[TripStop]]` olarak taşıyordu, bu test yalnızca gün
        // sınırlarının decode sırasında KAYBOLMADIĞINI doğruluyor (Milestone
        // 25'in gün navigasyonunun üzerine kurulduğu temel varsayım).
        let trip = try decode("""
        {
          "id": 3, "title": "Çok Günlü Gezi", "total_distance_km": 20.0,
          "created_at": null, "stops_count": 2, "days": [
            [{"place_id": 1, "name": "A", "latitude": 41.0, "longitude": 29.0, "city": null, "category": null, "day_index": 0, "order_index": 0}],
            [{"place_id": 2, "name": "B", "latitude": 42.0, "longitude": 30.0, "city": null, "category": null, "day_index": 1, "order_index": 0}]
          ],
          "applied_itinerary_id": null, "itinerary_applied_at": null
        }
        """)

        XCTAssertEqual(trip.days.count, 2)
        XCTAssertEqual(trip.allStops.count, 2)
        XCTAssertEqual(trip.days[0].first?.dayIndex, 0)
        XCTAssertEqual(trip.days[1].first?.dayIndex, 1)
    }
}
