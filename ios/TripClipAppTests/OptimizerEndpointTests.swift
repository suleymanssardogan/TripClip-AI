import XCTest
@testable import TripClipApp

/// AI Trip Optimizer için Endpoint → URLRequest çevrimi. Tamamen senkron/saf —
/// ağ yok, ViewModel yok; yalnızca `path`/`method`/`body`/header üretimini
/// doğrular (bkz. Endpoint.swift, docs/trip-optimizer-bff.md route tablosu).
final class OptimizerEndpointTests: XCTestCase {

    private let baseURL = URL(string: "https://api.tripclip.test")!

    // MARK: - optimizeTrip

    func test_optimizeTrip_pathAndMethod() throws {
        let request = try Endpoint.optimizeTrip(tripID: 42, placeIDs: [1, 2, 3])
            .urlRequest(baseURL: baseURL, token: nil)

        XCTAssertEqual(request.url?.path, "/api/mobile/trips/42/optimize")
        XCTAssertEqual(request.httpMethod, "POST")
    }

    func test_optimizeTrip_bodyContainsSelectedPlaceIDs() throws {
        let request = try Endpoint.optimizeTrip(tripID: 1, placeIDs: [12, 7, 19])
            .urlRequest(baseURL: baseURL, token: nil)

        let body = try XCTUnwrap(request.httpBody)
        let json = try XCTUnwrap(JSONSerialization.jsonObject(with: body) as? [String: Any])

        XCTAssertEqual(json["selected_place_ids"] as? [Int], [12, 7, 19])
        // start_date/duration_days/preferred_*_time/strategy kasıtlı olarak
        // gönderilmiyor — core-api'nin kendi varsayılanları kullanılır.
        XCTAssertEqual(json.count, 1)
    }

    func test_optimizeTrip_setsAuthorizationHeader_whenTokenProvided() throws {
        let request = try Endpoint.optimizeTrip(tripID: 1, placeIDs: [1])
            .urlRequest(baseURL: baseURL, token: "abc123")

        XCTAssertEqual(request.value(forHTTPHeaderField: "Authorization"), "Bearer abc123")
    }

    func test_optimizeTrip_omitsAuthorizationHeader_whenTokenNil() throws {
        let request = try Endpoint.optimizeTrip(tripID: 1, placeIDs: [1])
            .urlRequest(baseURL: baseURL, token: nil)

        XCTAssertNil(request.value(forHTTPHeaderField: "Authorization"))
    }

    // MARK: - itineraries (list)

    func test_itineraries_pathAndMethod() throws {
        let request = try Endpoint.itineraries(tripID: 7).urlRequest(baseURL: baseURL, token: nil)

        XCTAssertEqual(request.url?.path, "/api/mobile/trips/7/itineraries")
        XCTAssertEqual(request.httpMethod, "GET")
        XCTAssertNil(request.httpBody)
    }

    // MARK: - itineraryDetail

    func test_itineraryDetail_pathAndMethod() throws {
        let request = try Endpoint.itineraryDetail(itineraryID: 9).urlRequest(baseURL: baseURL, token: nil)

        XCTAssertEqual(request.url?.path, "/api/mobile/itineraries/9")
        XCTAssertEqual(request.httpMethod, "GET")
        XCTAssertNil(request.httpBody)
    }

    // MARK: - Decoding — gerçek mobile-bff/core-api yanıt şekli

    func test_decodesItinerary_fromRealisticServerJSON() throws {
        let json = """
        {
          "id": 4, "trip_id": 1, "strategy_name": "greedy_distance",
          "optimization_score": 87.5, "total_distance_km": 12.4, "total_travel_time_minutes": 29.8,
          "warnings": ["Açılış saatleri bilinmiyor: 2 mekan için program bu kısıt dikkate alınmadan oluşturuldu."],
          "created_at": "2026-08-08T10:00:00",
          "days": [{ "day_index": 0, "stops": [{
              "place_id": 12, "name": "Ayasofya", "lat": 41.0086, "lng": 28.9802,
              "day_index": 0, "order_index": 0,
              "arrival_time": "09:00", "departure_time": "09:30", "visit_duration_minutes": 30,
              "travel_time_to_next_minutes": 4.2, "travel_distance_to_next_km": 1.75
          }] }]
        }
        """.data(using: .utf8)!

        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        let itinerary = try decoder.decode(Itinerary.self, from: json)

        XCTAssertEqual(itinerary.id, 4)
        XCTAssertEqual(itinerary.tripId, 1)
        XCTAssertEqual(itinerary.optimizationScore, 87.5)
        XCTAssertEqual(itinerary.warnings.count, 1)
        XCTAssertEqual(itinerary.days.count, 1)
        let stop = try XCTUnwrap(itinerary.days.first?.stops.first)
        XCTAssertEqual(stop.placeId, 12)
        XCTAssertEqual(stop.arrivalTime, "09:00")
        XCTAssertEqual(stop.travelTimeToNextMinutes, 4.2)
    }

    func test_decodesItineraryStop_withNullPlaceFields_whenSourcePlaceWasDeleted() throws {
        // TripItineraryStop.place_id ondelete=SET NULL — bkz. OptimizerModels.swift.
        let json = """
        { "place_id": null, "name": "Silinmiş mekan", "lat": null, "lng": null,
          "day_index": 0, "order_index": 0, "arrival_time": null, "departure_time": null,
          "visit_duration_minutes": 60, "travel_time_to_next_minutes": null, "travel_distance_to_next_km": null }
        """.data(using: .utf8)!

        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        let stop = try decoder.decode(ItineraryStop.self, from: json)

        XCTAssertNil(stop.placeId)
        XCTAssertNil(stop.lat)
        XCTAssertEqual(stop.name, "Silinmiş mekan")
        XCTAssertTrue(stop.id.hasSuffix("deleted"))
    }

    func test_decodesItineraryListResponse() throws {
        // days_count/stops_count — Itinerary History listesinin days/stops'un
        // tamamını çekmeden özet gösterebilmesi için eklendi (bkz.
        // SqlOptimizationRepository.list_itineraries).
        let json = """
        { "itineraries": [
            { "id": 1, "trip_id": 1, "strategy_name": "greedy_distance",
              "optimization_score": 90.0, "total_distance_km": 5.0, "total_travel_time_minutes": 12.0,
              "warnings": [], "created_at": null, "days_count": 2, "stops_count": 5 }
        ] }
        """.data(using: .utf8)!

        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        let list = try decoder.decode(ItineraryListResponse.self, from: json)

        XCTAssertEqual(list.itineraries.count, 1)
        let summary = try XCTUnwrap(list.itineraries.first)
        XCTAssertEqual(summary.optimizationScore, 90.0)
        XCTAssertEqual(summary.daysCount, 2)
        XCTAssertEqual(summary.stopsCount, 5)
    }
}
