import Foundation

// MARK: - Library (kütüphane) — videolar-arası, tekilleştirilmiş mekanlar

struct LibraryPlace: Decodable, Identifiable, Hashable {
    let id:        Int
    let name:      String
    let latitude:  Double
    let longitude: Double
    let city:      String?
    let address:   String?
    let category:  String?
    let saveCount: Int
    let savedAt:   String?

    var formattedSavedAt: String {
        guard let raw = savedAt, let date = APIDate.parse(raw) else { return "" }
        return APIDate.displayString(from: date)
    }
}

struct LibraryResponse: Decodable {
    let places: [LibraryPlace]
    let total:  Int
}
