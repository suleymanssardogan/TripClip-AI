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
    /// İsteğin `start_date`'i verildiyse bu günün takvim tarihi
    /// (`"YYYY-MM-DD"`) — verilmediyse `nil` (bkz. Trip Planning Date
    /// milestone, docs/ios-trip-optimizer.md). Backend zaten hesaplıyor
    /// (`_date_for`, greedy_distance_strategy.py) — iOS burada hiçbir
    /// takvim aritmetiği YAPMIYOR, yalnızca gösteriyor.
    let date:     String?
    let stops:    [ItineraryStop]

    // Elle yazılmış, `date` için varsayılan değerli bir memberwise init —
    // property'nin kendi bildirimine `= nil` eklemek yerine burada (bkz.
    // Swift'in bilinen tuzağı: `let x: T = value` biçimindeki bir property,
    // sentezlenen `Decodable.init(from:)`'dan SESSİZCE HARİÇ TUTULUR, yani
    // `date` her zaman `nil` decode edilirdi — gerçek sunucu yanıtları dahil.
    // Bu elle yazılmış init, sentezlenen Decodable'a DOKUNMUYOR (yalnızca
    // kendi `init(from:)`'unuzu yazarsanız o etkilenir), yalnızca eski test
    // fixture'larının `date` belirtmeden derlenmeye devam etmesini sağlıyor.
    init(dayIndex: Int, date: String? = nil, stops: [ItineraryStop]) {
        self.dayIndex = dayIndex
        self.date = date
        self.stops = stops
    }

    var id: Int { dayIndex }

    /// "12 Ağustos 2026" — `date` yoksa `nil` (çağıran taraf `"1. Gün"` gibi
    /// bir sıra-numarası etiketine düşer, bkz. `ItineraryDaySection`).
    /// `Itinerary.formattedCreatedAt` ile AYNI desen, farklı ayrıştırıcı
    /// (`parseDateOnly` — bu alan `T`'li tam bir datetime DEĞİL, salt tarih).
    var formattedDate: String? {
        guard let date, let parsed = APIDate.parseDateOnly(date) else { return nil }
        return APIDate.displayString(from: parsed)
    }
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

// MARK: - Apply History & Undo — bkz. docs/ios-trip-optimizer.md "Apply
// History & Undo". Alan adları core-api'nin ApplyHistoryEntryResponse/
// UndoApplyResponse'uyla birebir eşleşir.

struct ApplyHistoryEntry: Decodable, Identifiable, Hashable {
    let id:                  Int
    /// `nil` — bu olayın sonucu itinerary-kökenli değil (ör. trip'in
    /// orijinal/manuel durak listesine dönen bir undo), YA DA kaynak
    /// itinerary sonradan silinmiş (`ondelete=SET NULL`). Bu ikisi
    /// `isUndo` ile birlikte ayırt edilir — bkz. `ItineraryApplyHistoryRowView`.
    let itineraryId:         Int?
    let itineraryCreatedAt:  String?
    let isUndo:              Bool
    let appliedAt:           String?
    let actorUserId:         Int
    let isUndoable:          Bool

    var formattedAppliedAt: String {
        guard let raw = appliedAt, let date = APIDate.parse(raw) else { return "" }
        return APIDate.displayString(from: date)
    }
}

struct ApplyHistoryListResponse: Decodable {
    let entries: [ApplyHistoryEntry]
}

struct UndoApplyResult: Decodable {
    let tripId:      Int
    let historyId:   Int
    let itineraryId: Int?
    let stops:       [AppliedTripStop]
    let stopsCount:  Int
    let appliedAt:   String?
}
