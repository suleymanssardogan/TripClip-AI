import Foundation

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
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        if let date = formatter.date(from: raw) {
            return date.formatted(.dateTime.day().month(.wide).year())
        }
        return raw
    }
}

struct PlanListResponse: Decodable {
    let plans: [PlanSummary]
    let total: Int
}

// MARK: - Plan Detail (ResultsView)

struct PlanDetail: Codable, Identifiable {
    let id:               Int
    let filename:         String
    let status:           String
    let duration:         Int?
    let createdAt:        String?
    let locations:        [LocationPin]
    let route:            [RoutePoint]?
    let transcription:    String?
    let travelTips:       [TravelTip]
    let ocrPois:          [String]
    let detectionsCount:  Int
    let processingTime:   Double?
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
