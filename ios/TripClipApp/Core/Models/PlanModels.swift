import Foundation

// MARK: - API Tarih Ayrıştırma

/// Backend'in gönderdiği tarih dizgilerini toleranslı biçimde çözer.
///
/// core-api `datetime.utcnow().isoformat()` kullanıyor; çıktı
/// `2026-07-29T07:23:20.116521` — timezone belirteci YOK. `ISO8601DateFormatter`
/// `.withInternetDateTime` ile zorunlu olarak `Z`/`±HH:MM` bekler, dolayısıyla
/// bu biçimde nil döner ve ekranda ham dizge kalırdı. Sunucu tarafı düzelene
/// kadar (ve sonrasında da, format oynamalarına karşı) sırayla deneriz.
enum APIDate {

    // nonisolated(unsafe): ISO8601DateFormatter Sendable değil ama burada bir kez
    // yapılandırılıp bir daha değiştirilmiyor; Apple yapılandırma sonrası
    // date(from:) çağrılarının thread-safe olduğunu belgeliyor. Swift 6 bunu tip
    // seviyesinde göremediği için elle işaretliyoruz. (DateFormatter zaten
    // Sendable olduğundan naiveUTC'de gerekmiyor.)
    nonisolated(unsafe) private static let internetWithFraction: ISO8601DateFormatter = {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return f
    }()

    nonisolated(unsafe) private static let internetDateTime: ISO8601DateFormatter = {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime]
        return f
    }()

    /// Timezone'suz varyant — UTC varsayılır (backend utcnow() kullanıyor).
    private static let naiveUTC: DateFormatter = {
        let f = DateFormatter()
        f.locale     = Locale(identifier: "en_US_POSIX")
        f.timeZone   = TimeZone(secondsFromGMT: 0)
        f.dateFormat = "yyyy-MM-dd'T'HH:mm:ss"
        return f
    }()

    static func parse(_ raw: String) -> Date? {
        if let date = internetWithFraction.date(from: raw) { return date }
        if let date = internetDateTime.date(from: raw)     { return date }
        // Kesirli saniyeyi at: "…T07:23:20.116521" → "…T07:23:20".
        // DateFormatter mikrosaniyeyi (6 hane) güvenilir ayrıştıramıyor.
        let withoutFraction = raw.split(separator: ".", maxSplits: 1).first.map(String.init) ?? raw
        return naiveUTC.date(from: withoutFraction)
    }

    /// Yalnızca-tarih (saat bileşeni YOK) varyant — core-api'nin
    /// `start_date`/`ItineraryDayResponse.date` gibi salt takvim tarihi
    /// alanları için: `"YYYY-MM-DD"`, Python'ın `datetime.date.isoformat()`'ı
    /// (bkz. `_date_for`, greedy_distance_strategy.py) — `created_at`'ın
    /// `T`'li tam datetime biçiminden KASITLI olarak farklı, bu yüzden
    /// yukarıdaki `parse(_:)` bunu ayrıştıramaz (üçü de bir `T` bekliyor).
    private static let dateOnly: DateFormatter = {
        let f = DateFormatter()
        f.locale     = Locale(identifier: "en_US_POSIX")
        f.timeZone   = TimeZone(secondsFromGMT: 0)
        f.dateFormat = "yyyy-MM-dd"
        return f
    }()

    /// Bkz. `dateOnly` — "2026-09-01" → `Date`. Geçersiz/eksik girdide `nil`.
    static func parseDateOnly(_ raw: String) -> Date? {
        dateOnly.date(from: raw)
    }

    /// Uygulama tamamen Türkçe — tarih de cihaz diline değil uygulamanın diline
    /// uymalı, yoksa "29 July 2026" gibi karışık bir sonuç çıkıyor.
    static let displayLocale = Locale(identifier: "tr_TR")

    /// "29 Temmuz 2026"
    static func displayString(from date: Date) -> String {
        date.formatted(
            .dateTime.day().month(.wide).year().locale(displayLocale)
        )
    }

    /// "12 Ağustos" — gün + ay, yıl YOK. `displayString`'in daha kısa
    /// varyantı; dar alanlarda (ör. gün seçici çipleri, bkz.
    /// `OptimizerMapDay.chipLabel`) yıl gereksiz/sığmıyor. Ay adı
    /// `Locale`'den geliyor (Foundation'ın `.dateTime.month(.wide)`
    /// `FormatStyle`'ı) — elle bir Türkçe ay adı tablosu tutulmuyor.
    static func shortDisplayString(from date: Date) -> String {
        date.formatted(
            .dateTime.day().month(.wide).locale(displayLocale)
        )
    }
}

// MARK: - Plan Summary (HomeView list)

struct PlanSummary: Decodable, Identifiable, Hashable {
    let id:             Int
    let filename:       String
    let status:         String
    let duration:       Int?
    let createdAt:      String?
    let locationsCount: Int
    let topLocation:    String?
    let processingTime: Double?

    var isCompleted: Bool {
        status.lowercased() == "completed"
    }

    var isProcessing: Bool {
        let s = status.lowercased()
        return s == "processing" || s == "uploaded" || s == "queued"
    }

    var displayTitle: String {
        if let top = topLocation, !top.isEmpty {
            return top.prefix(1).uppercased() + top.dropFirst() + " Gezisi"
        }
        let raw = filename
            .replacingOccurrences(of: #"\.[^.]+$"#, with: "", options: .regularExpression)
            .replacingOccurrences(of: "-", with: " ")
            .replacingOccurrences(of: "_", with: " ")
            .trimmingCharacters(in: .whitespaces)
        return raw.isEmpty ? "Gezi #\(id)" : raw.capitalized
    }

    var formattedDate: String {
        guard let raw = createdAt else { return "" }
        guard let date = APIDate.parse(raw) else { return "" }
        return APIDate.displayString(from: date)
    }
}

struct PlanListResponse: Decodable {
    let plans: [PlanSummary]
    let total: Int
}

/// Gövdesi anlamlı veri taşımayan yazma uçları (`{"success": true}`).
struct SuccessResponse: Decodable {
    let success: Bool
}

// MARK: - Plan Detail (ResultsView)

struct PlanDetail: Codable, Identifiable {
    let id:               Int
    let filename:         String
    let status:           String
    let duration:         Int?
    let createdAt:        String?
    // Kullanıcı durakları düzenleyebiliyor (silme/sıralama) — sunucu yanıtı
    // beklenmeden ekranın güncellenmesi için değiştirilebilir olmalı.
    var locations:        [LocationPin]
    var route:            [RoutePoint]?
    let transcription:    String?
    let travelTips:       [TravelTip]
    let ocrPois:          [String]
    let detectionsCount:  Int
    let processingTime:   Double?

    /// PlanSummary.displayTitle ile aynı kural — paylaşılan dosyaların adı da
    /// listede görünen başlıkla eşleşsin.
    var displayTitle: String {
        if let top = locations.first?.name, !top.isEmpty {
            return top.prefix(1).uppercased() + top.dropFirst() + " Gezisi"
        }
        return "Gezi #\(id)"
    }
}

struct LocationPin: Codable, Identifiable {
    let index:     Int
    let name:      String
    let type:      String
    let latitude:  Double
    let longitude: Double
    let importance: Double

    var id: Int { index }
}

struct RoutePoint: Codable {
    let latitude:  Double
    let longitude: Double
    let name:      String
}

struct TravelTip: Codable {
    let location: String
    let tip:      String
}

// MARK: - Stats

struct PlatformStats: Decodable {
    let totalVideos:     Int
    let completedVideos: Int
    let totalUsers:      Int
    let totalCities:     Int
}

// MARK: - Progress

struct ProgressResponse: Decodable {
    let stage:          String
    let percent:        Int
    let stale:          Bool?
    let elapsedSeconds: Int?
}
