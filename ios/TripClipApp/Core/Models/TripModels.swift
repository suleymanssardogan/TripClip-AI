import Foundation

// MARK: - Trip Builder — Library'den seçilen mekanlardan TSP ile rotalanmış gezi

struct TripStop: Decodable, Identifiable, Hashable {
    let placeId:    Int
    let name:       String
    let latitude:   Double
    let longitude:  Double
    let city:       String?
    let category:   String?
    let dayIndex:   Int
    let orderIndex: Int

    var id: Int { placeId }

    /// TripMapView/LocationCard, video sonuçlarıyla ortak kullanıldığı için
    /// LocationPin bekliyor — place_id kalıcı kimlik olarak index'e taşınır.
    var asLocationPin: LocationPin {
        LocationPin(
            index: placeId, name: name, type: category ?? "location",
            latitude: latitude, longitude: longitude, importance: 1.0
        )
    }
}

struct TripDetail: Decodable, Identifiable, Hashable {
    let id:               Int
    let title:            String
    let totalDistanceKm:  Double?
    let createdAt:        String?
    let stopsCount:       Int
    var days:              [[TripStop]]

    /// Şimdilik tek gün destekleniyor (bkz. sql_trip_repository.create_trip) —
    /// UI çok günlü gruplamayı zaten destekliyor, yalnızca oluşturma anında tek gün dolduruluyor.
    var allStops: [TripStop] { days.flatMap { $0 } }

    var formattedCreatedAt: String {
        guard let raw = createdAt, let date = APIDate.parse(raw) else { return "" }
        return APIDate.displayString(from: date)
    }
}

struct TripSummary: Decodable, Identifiable, Hashable {
    let id:              Int
    let title:           String
    let totalDistanceKm: Double?
    let createdAt:       String?
    let stopsCount:      Int

    var formattedCreatedAt: String {
        guard let raw = createdAt, let date = APIDate.parse(raw) else { return "" }
        return APIDate.displayString(from: date)
    }
}

struct TripListResponse: Decodable {
    let trips: [TripSummary]
}
