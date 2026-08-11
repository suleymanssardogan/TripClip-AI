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
        // preferred_start_time/end_time artık HER ZAMAN gönderiliyor (bkz.
        // "Preferred Start/End Time Controls" milestone) — çağıran taraf
        // belirtmezse core-api'nin kendi varsayılanlarıyla BİREBİR aynı
        // değerler gider (ClockTime.defaultStart/defaultEnd), field
        // atlanmaz. start_date/strategy kasıtlı olarak hâlâ gönderilmiyor —
        // core-api'nin kendi varsayılanları (greedy_distance) kullanılır.
        // duration_days ise (Otomatik/nil varsayılanla) burada eklenmiyor —
        // bkz. aşağıdaki test_optimizeTrip_bodyOmitsDurationDays_whenNil.
        XCTAssertEqual(json["preferred_start_time"] as? String, "09:00")
        XCTAssertEqual(json["preferred_end_time"] as? String, "18:00")
        XCTAssertEqual(json.count, 3)
    }

    func test_optimizeTrip_bodyOmitsDurationDays_whenNil() throws {
        // Optimizer Yapılandırma ekranında "Otomatik" seçiliyken (varsayılan,
        // bkz. TripOptimizerConfigViewModel) durationDays nil'dir — istek
        // gövdesine hiç eklenmemeli, backend kendi gün sayısını türetsin.
        let request = try Endpoint.optimizeTrip(tripID: 1, placeIDs: [1], durationDays: nil)
            .urlRequest(baseURL: baseURL, token: nil)
        let body = try XCTUnwrap(request.httpBody)
        let json = try XCTUnwrap(JSONSerialization.jsonObject(with: body) as? [String: Any])

        XCTAssertNil(json["duration_days"])
    }

    func test_optimizeTrip_bodyIncludesDurationDays_whenProvided() throws {
        let request = try Endpoint.optimizeTrip(tripID: 1, placeIDs: [12, 7], durationDays: 3)
            .urlRequest(baseURL: baseURL, token: nil)
        let body = try XCTUnwrap(request.httpBody)
        let json = try XCTUnwrap(JSONSerialization.jsonObject(with: body) as? [String: Any])

        XCTAssertEqual(json["selected_place_ids"] as? [Int], [12, 7])
        XCTAssertEqual(json["duration_days"] as? Int, 3)
        XCTAssertEqual(json.count, 4)
    }

    // MARK: - preferred_start_time / preferred_end_time

    func test_optimizeTrip_bodyIncludesCustomPreferredStartAndEndTime() throws {
        let request = try Endpoint.optimizeTrip(
            tripID: 1, placeIDs: [1],
            preferredStartTime: ClockTime(hour: 10, minute: 30),
            preferredEndTime: ClockTime(hour: 20, minute: 15)
        ).urlRequest(baseURL: baseURL, token: nil)
        let body = try XCTUnwrap(request.httpBody)
        let json = try XCTUnwrap(JSONSerialization.jsonObject(with: body) as? [String: Any])

        XCTAssertEqual(json["preferred_start_time"] as? String, "10:30")
        XCTAssertEqual(json["preferred_end_time"] as? String, "20:15")
    }

    /// Overnight Time Ranges milestone: bir overnight aralık (`end < start`)
    /// hâlâ AYNEN diğer her aralık gibi düz `"HH:MM"` dizgileri olarak
    /// gönderilir — özel bir kodlama, ek alan, ya da işaretleyici YOK (bkz.
    /// docs/ios-trip-optimizer.md "Overnight Time Ranges → API/DTO
    /// compatibility": `OptimizeTripRequest` hiç değişmedi).
    func test_optimizeTrip_bodySerializesOvernightRangeAsPlainHHMMStrings() throws {
        let request = try Endpoint.optimizeTrip(
            tripID: 1, placeIDs: [1],
            preferredStartTime: ClockTime(hour: 18, minute: 0),
            preferredEndTime: ClockTime(hour: 1, minute: 0)
        ).urlRequest(baseURL: baseURL, token: nil)
        let body = try XCTUnwrap(request.httpBody)
        let json = try XCTUnwrap(JSONSerialization.jsonObject(with: body) as? [String: Any])

        XCTAssertEqual(json["preferred_start_time"] as? String, "18:00")
        XCTAssertEqual(json["preferred_end_time"] as? String, "01:00")
    }

    /// Yalnızca başlangıç saati değiştirilmesi, gövdedeki bitiş saatini
    /// ETKİLEMEMELİ (spesifikasyonun kendi test gereksinimi).
    func test_optimizeTrip_changingOnlyStartTime_leavesEndTimeAtDefault() throws {
        let request = try Endpoint.optimizeTrip(
            tripID: 1, placeIDs: [1], preferredStartTime: ClockTime(hour: 7, minute: 0)
        ).urlRequest(baseURL: baseURL, token: nil)
        let body = try XCTUnwrap(request.httpBody)
        let json = try XCTUnwrap(JSONSerialization.jsonObject(with: body) as? [String: Any])

        XCTAssertEqual(json["preferred_start_time"] as? String, "07:00")
        XCTAssertEqual(json["preferred_end_time"] as? String, "18:00")   // ClockTime.defaultEnd, değişmedi
    }

    /// Yalnızca bitiş saati değiştirilmesi, gövdedeki başlangıç saatini
    /// ETKİLEMEMELİ.
    func test_optimizeTrip_changingOnlyEndTime_leavesStartTimeAtDefault() throws {
        let request = try Endpoint.optimizeTrip(
            tripID: 1, placeIDs: [1], preferredEndTime: ClockTime(hour: 22, minute: 0)
        ).urlRequest(baseURL: baseURL, token: nil)
        let body = try XCTUnwrap(request.httpBody)
        let json = try XCTUnwrap(JSONSerialization.jsonObject(with: body) as? [String: Any])

        XCTAssertEqual(json["preferred_start_time"] as? String, "09:00")  // ClockTime.defaultStart, değişmedi
        XCTAssertEqual(json["preferred_end_time"] as? String, "22:00")
    }

    // MARK: - start_date (Trip Planning Date — Req 4 "backward compatibility", Req 13 "request encoding")

    /// Geriye dönük uyumluluk: `startDate` belirtilmezse (varsayılan, bu
    /// milestone'dan önceki her istek gibi) `start_date` alanı gövdeye HİÇ
    /// eklenmemeli — `duration_days`'in "Otomatik" deseniyle AYNI.
    func test_optimizeTrip_bodyOmitsStartDate_whenNil() throws {
        let request = try Endpoint.optimizeTrip(tripID: 1, placeIDs: [1])
            .urlRequest(baseURL: baseURL, token: nil)
        let body = try XCTUnwrap(request.httpBody)
        let json = try XCTUnwrap(JSONSerialization.jsonObject(with: body) as? [String: Any])

        XCTAssertNil(json["start_date"])
    }

    func test_optimizeTrip_bodyIncludesStartDate_whenProvided() throws {
        let request = try Endpoint.optimizeTrip(
            tripID: 1, placeIDs: [1], startDate: PlanningDate(year: 2026, month: 9, day: 1)
        ).urlRequest(baseURL: baseURL, token: nil)
        let body = try XCTUnwrap(request.httpBody)
        let json = try XCTUnwrap(JSONSerialization.jsonObject(with: body) as? [String: Any])

        XCTAssertEqual(json["start_date"] as? String, "2026-09-01")
    }

    /// Tek haneli ay/gün doğru sıfır-doldurulmalı — core-api'nin
    /// `date.fromisoformat` ayrıştırıcısı yalnızca `"YYYY-MM-DD"` (iki
    /// haneli ay/gün) kabul eder.
    func test_optimizeTrip_bodyZeroPadsStartDate() throws {
        let request = try Endpoint.optimizeTrip(
            tripID: 1, placeIDs: [1], startDate: PlanningDate(year: 2026, month: 1, day: 5)
        ).urlRequest(baseURL: baseURL, token: nil)
        let body = try XCTUnwrap(request.httpBody)
        let json = try XCTUnwrap(JSONSerialization.jsonObject(with: body) as? [String: Any])

        XCTAssertEqual(json["start_date"] as? String, "2026-01-05")
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

    /// Trip Planning Date: `start_date` verilmiş bir istekten dönen gerçekçi
    /// bir yanıt şekli — her günün `date`'i doğru decode edilmeli. Bu, hem
    /// taze `.generate` yanıtı hem de Itinerary History'den `.viewSaved`
    /// yüklemesi için AYNI decode yolu (`Itinerary: Decodable`) — ayrı bir
    /// "kayıtlı itinerary" decode mantığı yok (Req 8).
    func test_decodesItinerary_withPerDayDate_whenStartDateWasProvided() throws {
        let json = """
        {
          "id": 4, "trip_id": 1, "strategy_name": "greedy_distance",
          "optimization_score": 87.5, "total_distance_km": 12.4, "total_travel_time_minutes": 29.8,
          "warnings": [], "created_at": "2026-08-08T10:00:00",
          "days": [
            { "day_index": 0, "date": "2026-09-01", "stops": [{
                "place_id": 12, "name": "Ayasofya", "lat": 41.0086, "lng": 28.9802,
                "day_index": 0, "order_index": 0,
                "arrival_time": "09:00", "departure_time": "09:30", "visit_duration_minutes": 30,
                "travel_time_to_next_minutes": null, "travel_distance_to_next_km": null
            }] },
            { "day_index": 1, "date": "2026-09-02", "stops": [{
                "place_id": 7, "name": "Topkapı Sarayı", "lat": 41.0115, "lng": 28.9833,
                "day_index": 1, "order_index": 0,
                "arrival_time": "09:00", "departure_time": "10:00", "visit_duration_minutes": 60,
                "travel_time_to_next_minutes": null, "travel_distance_to_next_km": null
            }] }
          ]
        }
        """.data(using: .utf8)!

        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        let itinerary = try decoder.decode(Itinerary.self, from: json)

        XCTAssertEqual(itinerary.days[0].date, "2026-09-01")
        XCTAssertEqual(itinerary.days[1].date, "2026-09-02")
        // Sıralı takvim günleri — 1'er gün artıyor, 24 saat DEĞİL (bkz.
        // PlanningDateTests, backend _date_for ile aynı garanti).
        XCTAssertEqual(itinerary.days[0].formattedDate, "1 Eylül 2026")
        XCTAssertEqual(itinerary.days[1].formattedDate, "2 Eylül 2026")
    }

    /// Geriye dönük uyumluluk: `date` alanı hiç YOKSA (bu milestone'dan
    /// önceki her yanıt gibi) decode başarısız olmamalı, `nil` olmalı.
    func test_decodesItinerary_withoutDateField_decodesNilGracefully() throws {
        let json = """
        { "day_index": 0, "stops": [] }
        """.data(using: .utf8)!

        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        let day = try decoder.decode(ItineraryDay.self, from: json)

        XCTAssertNil(day.date)
        XCTAssertNil(day.formattedDate)
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
