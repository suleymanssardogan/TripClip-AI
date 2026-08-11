import XCTest
@testable import TripClipApp

/// `OptimizerRouteMapData` — itinerary → harita sunum verisi. Tamamen saf/
/// senkron (MapKit'e bağımlı değil), bkz. docs/ios-trip-optimizer.md
/// "Map view" testability notu: harita ÇİZİMİ zor test edilebildiğinden, bu
/// dönüşüm ayrı ve MapKit'siz test edilir.
final class OptimizerRouteMapDataTests: XCTestCase {

    private func stop(
        placeId: Int? = 1, name: String = "Mekan", lat: Double? = 41.0, lng: Double? = 29.0,
        dayIndex: Int = 0, orderIndex: Int = 0
    ) -> ItineraryStop {
        ItineraryStop(
            placeId: placeId, name: name, lat: lat, lng: lng,
            dayIndex: dayIndex, orderIndex: orderIndex,
            arrivalTime: nil, departureTime: nil, visitDurationMinutes: 30,
            travelTimeToNextMinutes: nil, travelDistanceToNextKm: nil
        )
    }

    // MARK: - One-stop itinerary

    func test_oneStopItinerary_producesSingleDayWithOneStop_noPolylineNeeded() {
        let itinerary = OptimizerFixtures.itinerary(days: [
            ItineraryDay(dayIndex: 0, stops: [stop(placeId: 1, name: "Ayasofya", dayIndex: 0, orderIndex: 0)])
        ])

        let data = OptimizerRouteMapData(itinerary: itinerary)

        XCTAssertFalse(data.isEmpty)
        XCTAssertFalse(data.hasMultipleDays)
        XCTAssertEqual(data.days.count, 1)
        XCTAssertEqual(data.days[0].stops.count, 1)
        XCTAssertEqual(data.missingCoordinateCount, 0)
    }

    // MARK: - Multiple stops (single day)

    func test_multipleStops_singleDay_preservesOrderAndCoordinates() {
        let itinerary = OptimizerFixtures.itinerary(days: [OptimizerFixtures.oneDayWithTwoStops])

        let data = OptimizerRouteMapData(itinerary: itinerary)

        XCTAssertEqual(data.days.count, 1)
        let stops = data.days[0].stops
        XCTAssertEqual(stops.map(\.name), ["Ayasofya", "Topkapı Sarayı"])
        XCTAssertEqual(stops.map(\.orderIndex), [0, 1])
        XCTAssertEqual(stops[0].latitude, 41.0086)
        XCTAssertEqual(stops[0].longitude, 28.9802)
    }

    // MARK: - Multiple days

    func test_multipleDays_keepsDaysSeparate_hasMultipleDaysTrue() {
        let itinerary = OptimizerFixtures.itinerary(days: [
            ItineraryDay(dayIndex: 0, stops: [
                stop(placeId: 1, name: "Gün1-A", dayIndex: 0, orderIndex: 0),
                stop(placeId: 2, name: "Gün1-B", dayIndex: 0, orderIndex: 1),
            ]),
            ItineraryDay(dayIndex: 1, stops: [
                stop(placeId: 3, name: "Gün2-A", dayIndex: 1, orderIndex: 0),
            ]),
        ])

        let data = OptimizerRouteMapData(itinerary: itinerary)

        XCTAssertTrue(data.hasMultipleDays)
        XCTAssertEqual(data.days.count, 2)
        XCTAssertEqual(data.days[0].stops.map(\.name), ["Gün1-A", "Gün1-B"])
        XCTAssertEqual(data.days[1].stops.map(\.name), ["Gün2-A"])
        // Her günün kendi durak dizisi var — Day 1'in son durağı Day 2'nin
        // ilk durağıyla aynı diziye ASLA karışmıyor (Req 2).
        XCTAssertFalse(data.days[0].stops.map(\.name).contains("Gün2-A"))
    }

    func test_dayIndices_areNotRenumbered_evenIfFirstDayHasNoUsableCoordinates() {
        // Gün 0'ın TÜM durakları koordinatsızsa o gün haritada hiç görünmez,
        // ama kalan günün dayIndex'i "1" olarak kalmalı (0'a kaymamalı) —
        // aksi halde gün etiketleri yanlış gösterilir.
        let itinerary = OptimizerFixtures.itinerary(days: [
            ItineraryDay(dayIndex: 0, stops: [stop(placeId: 1, lat: nil, lng: nil, dayIndex: 0, orderIndex: 0)]),
            ItineraryDay(dayIndex: 1, stops: [stop(placeId: 2, name: "Gün2", dayIndex: 1, orderIndex: 0)]),
        ])

        let data = OptimizerRouteMapData(itinerary: itinerary)

        XCTAssertEqual(data.days.count, 1)
        XCTAssertEqual(data.days[0].dayIndex, 1)
    }

    // MARK: - Missing coordinates

    func test_missingCoordinates_areOmittedFromMap_butCounted_doesNotCrash() {
        let itinerary = OptimizerFixtures.itinerary(days: [
            ItineraryDay(dayIndex: 0, stops: [
                stop(placeId: 1, name: "Koordinatlı", lat: 41.0, lng: 29.0, dayIndex: 0, orderIndex: 0),
                stop(placeId: 2, name: "Koordinatsız", lat: nil, lng: nil, dayIndex: 0, orderIndex: 1),
                stop(placeId: 3, name: "Koordinatlı2", lat: 41.1, lng: 29.1, dayIndex: 0, orderIndex: 2),
            ])
        ])

        let data = OptimizerRouteMapData(itinerary: itinerary)

        XCTAssertEqual(data.missingCoordinateCount, 1)
        XCTAssertEqual(data.days[0].stops.map(\.name), ["Koordinatlı", "Koordinatlı2"])
        // orderIndex boşluk bırakarak korunuyor (0, 2) — atlanan durak yüzünden
        // yeniden numaralandırılmıyor.
        XCTAssertEqual(data.days[0].stops.map(\.orderIndex), [0, 2])
    }

    func test_allStopsMissingCoordinates_producesEmptyDays_withFullMissingCount() {
        let itinerary = OptimizerFixtures.itinerary(days: [
            ItineraryDay(dayIndex: 0, stops: [
                stop(placeId: 1, lat: nil, lng: nil, dayIndex: 0, orderIndex: 0),
                stop(placeId: 2, lat: nil, lng: nil, dayIndex: 0, orderIndex: 1),
            ])
        ])

        let data = OptimizerRouteMapData(itinerary: itinerary)

        XCTAssertTrue(data.isEmpty)
        XCTAssertEqual(data.missingCoordinateCount, 2)
        XCTAssertTrue(data.allStops.isEmpty)
    }

    /// Silinmiş bir kaynak Place — placeId nil ama lat/lng de nil olabilir
    /// (bkz. ItineraryStop doc yorumu, TripItineraryStop.place_id ondelete
    /// SET NULL). Bu durumda da crash olmamalı, yalnızca atlanmalı.
    func test_deletedSourcePlace_withNilPlaceIdAndCoordinates_isOmittedGracefully() {
        let itinerary = OptimizerFixtures.itinerary(days: [
            ItineraryDay(dayIndex: 0, stops: [
                stop(placeId: nil, name: "Silinmiş mekan", lat: nil, lng: nil, dayIndex: 0, orderIndex: 0),
            ])
        ])

        let data = OptimizerRouteMapData(itinerary: itinerary)

        XCTAssertTrue(data.isEmpty)
        XCTAssertEqual(data.missingCoordinateCount, 1)
    }

    // MARK: - Saved itinerary rendering data

    /// `OptimizerRouteMapData` yalnızca bir `Itinerary` değeri alır —
    /// `.generate` ile mi `.viewSaved` (loadItinerary) ile mi geldiğinin
    /// farkında değil. Bu test, kayıtlı bir itinerary'nin (loadItinerary'nin
    /// döndürdüğü şekil) haritaya aynı şekilde dönüştüğünü doğruluyor.
    func test_savedItineraryShape_mapsIdenticallyToFreshlyGeneratedItinerary() {
        let saved = OptimizerFixtures.itinerary(id: 9, days: [OptimizerFixtures.oneDayWithTwoStops])

        let data = OptimizerRouteMapData(itinerary: saved)

        XCTAssertFalse(data.isEmpty)
        XCTAssertEqual(data.days[0].stops.count, 2)
        XCTAssertEqual(data.missingCoordinateCount, 0)
    }

    // MARK: - Day selection

    func test_visibleDays_nilSelection_returnsAllDays() {
        let itinerary = OptimizerFixtures.itinerary(days: [
            ItineraryDay(dayIndex: 0, stops: [stop(placeId: 1, dayIndex: 0, orderIndex: 0)]),
            ItineraryDay(dayIndex: 1, stops: [stop(placeId: 2, dayIndex: 1, orderIndex: 0)]),
        ])
        let data = OptimizerRouteMapData(itinerary: itinerary)

        XCTAssertEqual(data.visibleDays(selectedDayIndex: nil).count, 2)
    }

    func test_visibleDays_specificSelection_returnsOnlyThatDay() {
        let itinerary = OptimizerFixtures.itinerary(days: [
            ItineraryDay(dayIndex: 0, stops: [stop(placeId: 1, name: "Gün1", dayIndex: 0, orderIndex: 0)]),
            ItineraryDay(dayIndex: 1, stops: [stop(placeId: 2, name: "Gün2", dayIndex: 1, orderIndex: 0)]),
        ])
        let data = OptimizerRouteMapData(itinerary: itinerary)

        let visible = data.visibleDays(selectedDayIndex: 1)

        XCTAssertEqual(visible.count, 1)
        XCTAssertEqual(visible[0].dayIndex, 1)
        XCTAssertEqual(visible[0].stops.map(\.name), ["Gün2"])
    }

    func test_visibleDays_selectionMatchingNoDay_returnsEmpty() {
        let itinerary = OptimizerFixtures.itinerary(days: [OptimizerFixtures.oneDayWithTwoStops])
        let data = OptimizerRouteMapData(itinerary: itinerary)

        XCTAssertTrue(data.visibleDays(selectedDayIndex: 99).isEmpty)
    }

    // MARK: - Correct stop ordering across days

    func test_stopOrdering_isPreservedPerDay_independentOfOtherDays() {
        let itinerary = OptimizerFixtures.itinerary(days: [
            ItineraryDay(dayIndex: 0, stops: [
                stop(placeId: 1, name: "A", dayIndex: 0, orderIndex: 0),
                stop(placeId: 2, name: "B", dayIndex: 0, orderIndex: 1),
                stop(placeId: 3, name: "C", dayIndex: 0, orderIndex: 2),
            ]),
            ItineraryDay(dayIndex: 1, stops: [
                stop(placeId: 4, name: "D", dayIndex: 1, orderIndex: 0),
                stop(placeId: 5, name: "E", dayIndex: 1, orderIndex: 1),
            ]),
        ])

        let data = OptimizerRouteMapData(itinerary: itinerary)

        XCTAssertEqual(data.days[0].stops.map(\.name), ["A", "B", "C"])
        XCTAssertEqual(data.days[1].stops.map(\.name), ["D", "E"])
    }

    // MARK: - Empty itinerary days array

    func test_noDays_producesEmptyMapData() {
        let itinerary = OptimizerFixtures.itinerary(days: OptimizerFixtures.emptyDays)

        let data = OptimizerRouteMapData(itinerary: itinerary)

        XCTAssertTrue(data.isEmpty)
        XCTAssertEqual(data.missingCoordinateCount, 0)
        XCTAssertFalse(data.hasMultipleDays)
    }

    // MARK: - stop(withID:) — Bidirectional Itinerary ↔ Map Interaction milestone

    /// Req 3 "stable identity": haritalanmış durağın kimliği, kaynak
    /// `ItineraryStop.id` ile BİREBİR aynı — array index'e değil, sunucunun
    /// `day_index-order_index-place_id` üçlüsünden türetilen kararlı
    /// kimliğe dayanır. Bu, `OptimizerSelection.stopID`'nin harita ve
    /// itinerary listesi arasında güvenilir biçimde köprü kurabilmesinin
    /// temelidir.
    func test_stopWithID_stableIdentity_matchesSourceItineraryStopID() {
        let source = stop(placeId: 12, name: "Ayasofya", dayIndex: 0, orderIndex: 1)
        let itinerary = OptimizerFixtures.itinerary(days: [
            ItineraryDay(dayIndex: 0, stops: [
                stop(placeId: 99, dayIndex: 0, orderIndex: 0), source,
            ])
        ])

        let data = OptimizerRouteMapData(itinerary: itinerary)
        let mapStop = data.stop(withID: source.id)

        XCTAssertEqual(mapStop?.id, source.id)
        XCTAssertEqual(mapStop?.name, "Ayasofya")
    }

    /// Req 3: aynı durak, gün seçimi/filtrelemesi değişse bile AYNI id ile
    /// bulunabilir — `stop(withID:)` `visibleDays` filtrelemesinden
    /// bağımsız, `days` bütününde arar.
    func test_stopWithID_findsStop_regardlessOfWhichDayIsCurrentlySelected() {
        let target = stop(placeId: 7, name: "Gün2Durağı", dayIndex: 1, orderIndex: 0)
        let itinerary = OptimizerFixtures.itinerary(days: [
            ItineraryDay(dayIndex: 0, stops: [stop(placeId: 1, dayIndex: 0, orderIndex: 0)]),
            ItineraryDay(dayIndex: 1, stops: [target]),
        ])
        let data = OptimizerRouteMapData(itinerary: itinerary)

        // Gün 0 seçiliyken bile (visibleDays yalnızca gün 0'ı döner),
        // stop(withID:) TÜM günler içinde arar — harita, kullanıcı henüz
        // o güne geçmemiş olsa bile hangi durağa odaklanacağını bulabilir.
        XCTAssertTrue(data.visibleDays(selectedDayIndex: 0).allSatisfy { $0.dayIndex == 0 })
        XCTAssertEqual(data.stop(withID: target.id)?.dayIndex, 1)
        XCTAssertEqual(data.stop(withID: target.id)?.name, "Gün2Durağı")
    }

    /// Req 9 "the map should not attempt to center on an invalid
    /// coordinate": koordinatı olmayan bir durak `stop(withID:)` ile hiç
    /// BULUNAMAZ (zaten `init`'te elendi) — `OptimizerRouteMap` bu nil'i
    /// görüp hiçbir kamera işlemi yapmaz, crash olmaz.
    func test_stopWithID_missingCoordinateStop_returnsNil_doesNotCrash() {
        let missingCoordStop = stop(placeId: 5, name: "Koordinatsız", lat: nil, lng: nil, dayIndex: 0, orderIndex: 0)
        let itinerary = OptimizerFixtures.itinerary(days: [
            ItineraryDay(dayIndex: 0, stops: [missingCoordStop])
        ])
        let data = OptimizerRouteMapData(itinerary: itinerary)

        XCTAssertNil(data.stop(withID: missingCoordStop.id))
    }

    func test_stopWithID_unknownID_returnsNil() {
        let itinerary = OptimizerFixtures.itinerary(days: [OptimizerFixtures.oneDayWithTwoStops])
        let data = OptimizerRouteMapData(itinerary: itinerary)

        XCTAssertNil(data.stop(withID: "nonexistent-id"))
    }

    /// Saved itinerary etkileşimi: `stop(withID:)` yalnızca bir `Itinerary`
    /// değerine bakar, `.generate` ile mi `.viewSaved` ile mi geldiğinin
    /// farkında değil — aynı mekanizma her iki modda da aynı şekilde çalışır.
    func test_stopWithID_worksIdenticallyForSavedItineraryShape() {
        let saved = OptimizerFixtures.itinerary(id: 9, days: [OptimizerFixtures.oneDayWithTwoStops])
        let data = OptimizerRouteMapData(itinerary: saved)

        let firstStopID = OptimizerFixtures.oneDayWithTwoStops.stops[0].id
        XCTAssertEqual(data.stop(withID: firstStopID)?.name, "Ayasofya")
    }

    /// Req 9 "the selected itinerary row can still be highlighted" (even
    /// with no usable coordinate): `ItineraryDaySection`/`ItineraryStopRow`
    /// vurgulamayı `stop.id == selectedStopID` karşılaştırmasıyla yapar —
    /// `ItineraryStop.id` sunucudan gelen `dayIndex`/`orderIndex`/`placeId`
    /// üçlüsünden türetilir, lat/lng'e HİÇ bakmaz. Koordinatı olmayan bir
    /// durağın kimliği de aynı şekilde kararlı/karşılaştırılabilir kalır —
    /// itinerary listesindeki vurgulama, haritanın o durağı hiç
    /// gösteremiyor olmasından tamamen bağımsızdır.
    func test_itineraryStopID_isStableAndComparable_evenWithoutCoordinates() {
        let missingCoordStop = stop(placeId: 5, name: "Koordinatsız", lat: nil, lng: nil, dayIndex: 0, orderIndex: 2)
        let sameStopAgain    = stop(placeId: 5, name: "Koordinatsız", lat: nil, lng: nil, dayIndex: 0, orderIndex: 2)

        XCTAssertFalse(missingCoordStop.id.isEmpty)
        XCTAssertEqual(missingCoordStop.id, sameStopAgain.id)
        XCTAssertEqual(missingCoordStop.id, "0-2-5")   // dayIndex-orderIndex-placeId
    }

    // MARK: - Date-aware Map Day Selector milestone

    /// `OptimizerRouteMapData.init` her `ItineraryDay.date`'i ilgili
    /// `OptimizerMapDay.date`'e AYNEN taşır — burada hiçbir dönüşüm/
    /// yeniden hesaplama yok.
    func test_init_propagatesItineraryDayDate_intoOptimizerMapDay() {
        let itinerary = OptimizerFixtures.itinerary(days: [
            ItineraryDay(dayIndex: 0, date: "2026-08-12", stops: [stop(dayIndex: 0, orderIndex: 0)])
        ])
        let data = OptimizerRouteMapData(itinerary: itinerary)

        XCTAssertEqual(data.days[0].date, "2026-08-12")
    }

    /// Persistent Optimizer Route Cache milestone: `Itinerary.id` her günün
    /// `OptimizerMapDay.itineraryID`'sine aynen taşınmalı — rota önbellek
    /// anahtarının itinerary izolasyonu (Req 4) buna dayanıyor, bkz.
    /// `OptimizerRouteCalculator.cacheKey`/`legKey`.
    func test_init_propagatesItineraryID_intoOptimizerMapDay() {
        let itinerary = OptimizerFixtures.itinerary(
            id: 42,
            days: [ItineraryDay(dayIndex: 0, stops: [stop(dayIndex: 0, orderIndex: 0)])]
        )
        let data = OptimizerRouteMapData(itinerary: itinerary)

        XCTAssertEqual(data.days[0].itineraryID, 42)
    }

    /// Req 1: tarih varsa çip etiketi "12 Ağustos" — yıl YOK, ham ISO
    /// dizgisi ("2026-08-12") HİÇ gösterilmez.
    func test_chipLabel_withDate_showsDayAndMonth_noYear_noRawISOString() {
        let day = OptimizerMapDay(dayIndex: 0, date: "2026-08-12", stops: [
            OptimizerMapStop(id: "1", dayIndex: 0, orderIndex: 0, name: "A", latitude: 41, longitude: 29)
        ])

        XCTAssertEqual(day.chipLabel, "12 Ağustos")
        XCTAssertFalse(day.chipLabel.contains("2026"))
        XCTAssertFalse(day.chipLabel.contains("-"))
    }

    /// Req 2: `date == nil` → eski sıra-numarası etiketine düş (geriye dönük
    /// uyumluluk, tarihsiz/eski kayıtlı itinerary'ler).
    func test_chipLabel_withoutDate_fallsBackToOrdinalLabel() {
        let day = OptimizerMapDay(dayIndex: 0, date: nil, stops: [
            OptimizerMapStop(id: "1", dayIndex: 0, orderIndex: 0, name: "A", latitude: 41, longitude: 29)
        ])

        XCTAssertEqual(day.chipLabel, "1. Gün")
    }

    /// Bozuk/ayrıştırılamayan bir `date` dizgisi de (Req 9 "malformed/
    /// invalid date safely falls back") crash etmeden aynı geriye dönük
    /// düşüşe gitmeli — `APIDate.parseDateOnly` zaten `nil` döner, burada
    /// ekstra bir doğrulama YAPILMIYOR, yalnızca sonucu ele alıyoruz.
    func test_chipLabel_withMalformedDateString_fallsBackSafely_doesNotCrash() {
        let day = OptimizerMapDay(dayIndex: 2, date: "not-a-real-date", stops: [
            OptimizerMapStop(id: "1", dayIndex: 2, orderIndex: 0, name: "A", latitude: 41, longitude: 29)
        ])

        XCTAssertEqual(day.chipLabel, "3. Gün")
    }

    /// Req: "multiple consecutive dates" — art arda günlerin her biri
    /// kendi tarihini doğru gösterir, birbirine karışmaz. Aritmetik burada
    /// YAPILMIYOR (backend zaten hesapladı) — yalnızca üç ayrı, zaten-doğru
    /// dizgi doğru biçimlendiriliyor mu diye bakılıyor.
    func test_chipLabel_multipleConsecutiveDates_eachDayFormatsIndependently() {
        let itinerary = OptimizerFixtures.itinerary(days: [
            ItineraryDay(dayIndex: 0, date: "2026-08-12", stops: [stop(placeId: 1, dayIndex: 0, orderIndex: 0)]),
            ItineraryDay(dayIndex: 1, date: "2026-08-13", stops: [stop(placeId: 2, dayIndex: 1, orderIndex: 0)]),
            ItineraryDay(dayIndex: 2, date: "2026-08-14", stops: [stop(placeId: 3, dayIndex: 2, orderIndex: 0)]),
        ])
        let data = OptimizerRouteMapData(itinerary: itinerary)

        XCTAssertEqual(data.days.map(\.chipLabel), ["12 Ağustos", "13 Ağustos", "14 Ağustos"])
    }

    /// Saved itinerary (Itinerary History'den `.viewSaved`) ile taze
    /// `.generate` sonucu AYNI mekanizmadan geçer — `OptimizerRouteMapData`
    /// hangi moddan geldiğini bilmez/farklı davranmaz.
    func test_chipLabel_worksIdenticallyForSavedItineraryShape() {
        let saved = OptimizerFixtures.itinerary(id: 9, days: [
            ItineraryDay(dayIndex: 0, date: "2026-09-01", stops: [stop(dayIndex: 0, orderIndex: 0)])
        ])
        let data = OptimizerRouteMapData(itinerary: saved)

        XCTAssertEqual(data.days[0].chipLabel, "1 Eylül")
    }

    /// Req 3: gün seçim KİMLİĞİ hâlâ yalnızca `dayIndex` — `Identifiable`
    /// uygunluğu (`id`) tarih eklendikten SONRA da `dayIndex`'e dayanıyor,
    /// tarihe değil (aynı tarihe sahip iki farklı gün asla aynı `id`'yi
    /// paylaşmaz, farklı tarihli iki gün de `dayIndex` aynıysa aynı `id`'yi
    /// paylaşır — pratikte olmaz ama mekanizma yalnızca `dayIndex`'i okur).
    func test_id_stillDerivesFromDayIndex_notDate() {
        let day = OptimizerMapDay(dayIndex: 3, date: "2026-08-12", stops: [
            OptimizerMapStop(id: "1", dayIndex: 3, orderIndex: 0, name: "A", latitude: 41, longitude: 29)
        ])
        XCTAssertEqual(day.id, 3)
    }

    // MARK: - chipAccessibilityLabel (Req 7)

    func test_chipAccessibilityLabel_withDate_includesDayNumberAndDate() {
        let day = OptimizerMapDay(dayIndex: 0, date: "2026-08-12", stops: [
            OptimizerMapStop(id: "1", dayIndex: 0, orderIndex: 0, name: "A", latitude: 41, longitude: 29)
        ])
        XCTAssertEqual(day.chipAccessibilityLabel, "1. gün, 12 Ağustos")
    }

    func test_chipAccessibilityLabel_withoutDate_stillIdentifiesTheDayNumber() {
        let day = OptimizerMapDay(dayIndex: 1, date: nil, stops: [
            OptimizerMapStop(id: "1", dayIndex: 1, orderIndex: 0, name: "A", latitude: 41, longitude: 29)
        ])
        XCTAssertEqual(day.chipAccessibilityLabel, "2. gün")
    }
}
