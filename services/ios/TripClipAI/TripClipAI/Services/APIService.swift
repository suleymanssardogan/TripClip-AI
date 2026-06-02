import Foundation

class APIService {
    static let shared = APIService()
    private let baseURL = "http://172.20.10.6:8001"

    
    private let session: URLSession = {
        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = 300
        config.timeoutIntervalForResource = 300
        return URLSession(configuration: config)
    }()
    
    private func authHeader() -> String? {
        AuthService.shared.accessToken.map { "Bearer \($0)" }
    }

    // Video upload
    func uploadVideo(fileURL: URL) async throws -> Int {
        let url = URL(string: "\(baseURL)/api/mobile/videos/upload")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        if let auth = authHeader() { request.setValue(auth, forHTTPHeaderField: "Authorization") }
        
        let boundary = UUID().uuidString
        request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")
        
        var body = Data()
        let videoData = try Data(contentsOf: fileURL)
        let filename = fileURL.lastPathComponent
        
        body.append("--\(boundary)\r\n".data(using: .utf8)!)
        body.append("Content-Disposition: form-data; name=\"file\"; filename=\"\(filename)\"\r\n".data(using: .utf8)!)
        body.append("Content-Type: video/mp4\r\n\r\n".data(using: .utf8)!)
        body.append(videoData)
        body.append("\r\n--\(boundary)--\r\n".data(using: .utf8)!)
        
        request.httpBody = body
        
        let (data, httpResponse) = try await session.data(for: request)
        if let http = httpResponse as? HTTPURLResponse, http.statusCode >= 400 {
            let raw = String(data: data, encoding: .utf8) ?? "no body"
            throw NSError(domain: "API", code: http.statusCode,
                          userInfo: [NSLocalizedDescriptionKey: "HTTP \(http.statusCode): \(raw)"])
        }
        let response = try JSONDecoder().decode(UploadResponse.self, from: data)
        return response.id
    }

    // Video progress (stage + percent)
    func getVideoProgress(id: Int) async throws -> ProgressResponse {
        let url = URL(string: "\(baseURL)/api/mobile/videos/\(id)/progress")!
        var request = URLRequest(url: url)
        request.timeoutInterval = 10
        if let auth = authHeader() { request.setValue(auth, forHTTPHeaderField: "Authorization") }
        let (data, httpResponse) = try await session.data(for: request)
        if let http = httpResponse as? HTTPURLResponse, http.statusCode >= 400 {
            throw NSError(domain: "API", code: http.statusCode,
                          userInfo: [NSLocalizedDescriptionKey: "Progress unavailable"])
        }
        return try JSONDecoder().decode(ProgressResponse.self, from: data)
    }

    // Video status
    func getVideoStatus(id: Int) async throws -> VideoResponse {
        let url = URL(string: "\(baseURL)/api/mobile/videos/\(id)")!
        var request = URLRequest(url: url)
        if let auth = authHeader() { request.setValue(auth, forHTTPHeaderField: "Authorization") }
        let (data, httpResponse) = try await session.data(for: request)
        if let http = httpResponse as? HTTPURLResponse, http.statusCode >= 400 {
            let raw = String(data: data, encoding: .utf8) ?? "no body"
            throw NSError(domain: "API", code: http.statusCode,
                          userInfo: [NSLocalizedDescriptionKey: "HTTP \(http.statusCode): \(raw)"])
        }
        return try JSONDecoder().decode(VideoResponse.self, from: data)
    }

    /// Mevcut kullanıcının tüm videolarını getir (HistoryView senkronizasyonu için)
    func getMyVideos() async throws -> [VideoSummary] {
        let url = URL(string: "\(baseURL)/api/mobile/videos")!
        var request = URLRequest(url: url)
        if let auth = authHeader() { request.setValue(auth, forHTTPHeaderField: "Authorization") }
        let (data, httpResponse) = try await session.data(for: request)
        if let http = httpResponse as? HTTPURLResponse, http.statusCode >= 400 {
            throw NSError(domain: "API", code: http.statusCode,
                          userInfo: [NSLocalizedDescriptionKey: "Video listesi alınamadı"])
        }
        let resp = try JSONDecoder().decode(VideoListResponse.self, from: data)
        return resp.plans
    }

    // Queue Instagram/YouTube URL for background processing
    func queueURL(sourceURL: String) async throws -> Int {
        let url = URL(string: "\(baseURL)/api/mobile/videos/queue-url")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.timeoutInterval = 15
        if let auth = authHeader() { request.setValue(auth, forHTTPHeaderField: "Authorization") }
        request.httpBody = try JSONEncoder().encode(["source_url": sourceURL])

        let (data, httpResponse) = try await session.data(for: request)
        if let http = httpResponse as? HTTPURLResponse, http.statusCode >= 400 {
            let raw = String(data: data, encoding: .utf8) ?? "no body"
            throw NSError(domain: "API", code: http.statusCode,
                          userInfo: [NSLocalizedDescriptionKey: "HTTP \(http.statusCode): \(raw)"])
        }
        let response = try JSONDecoder().decode(UploadResponse.self, from: data)
        return response.id
    }
}

// Models
// MARK: - Video List (HistoryView için)

struct VideoListResponse: Codable {
    let plans: [VideoSummary]
    let total: Int
}

struct VideoSummary: Codable {
    let id: Int
    let filename: String?
    let status: String
    let duration: Int?
    let createdAt: String?
    let locationsCount: Int?
    let topLocation: String?
    let processingTime: Double?
}

struct ProgressResponse: Codable {
    let stage: String?
    let percent: Int?
    let elapsedSeconds: Int?
    let stale: Bool?

    enum CodingKeys: String, CodingKey {
        case stage, percent, stale
        case elapsedSeconds = "elapsed_seconds"
    }
}

struct UploadResponse: Codable {
    let id: Int
    let status: String
    let message: String
}

struct VideoResponse: Codable {
    let id: Int
    let filename: String
    let status: String
    let duration: Int?
    let createdAt: String?

    // ── Mobile BFF transformer çıktısı (flat alanlar) ──────────────────────
    // /api/mobile/videos/{id} bu alanları döndürür
    let locations:      [MobileLocation]?    // harita pinleri
    let route:          [RoutePoint]?        // TSP sırası
    let travelTips:     [Tip]?               // RAG ipuçları
    let transcription:  String?              // Whisper metni (düz string)
    let ocrPois:        [String]?            // OCR mekan isimleri
    let detectionsCount: Int?
    let processingTime:  Double?

    // ── Eski CoreData / offline format (HistoryView) ────────────────────────
    let aiResults: AIResults?

    enum CodingKeys: String, CodingKey {
        case id, filename, status, duration, route, transcription
        case createdAt       = "createdAt"
        case locations       = "locations"
        case travelTips      = "travelTips"
        case ocrPois         = "ocrPois"
        case detectionsCount = "detectionsCount"
        case processingTime  = "processingTime"
        case aiResults       = "ai_results"
    }

    // ── Birleşik erişim: Mobile BFF flat → EnrichedLocation dönüşümü ───────
    /// ResultsView bu özelliği kullanır — hem online hem offline çalışır.
    var enrichedLocations: [EnrichedLocation] {
        if let locs = locations, !locs.isEmpty {
            return locs.map { ml in
                EnrichedLocation(
                    originalName: ml.name,
                    placeData: PlaceData(
                        name: ml.name,
                        type: ml.type,
                        category: ml.type,
                        importance: ml.importance,
                        location: LocationCoordinate(lat: ml.latitude, lng: ml.longitude)
                    )
                )
            }
        }
        // Offline (CoreData) fallback
        return aiResults?.nominatim?.deduplicatedLocations ?? []
    }

    /// Seyahat ipuçları — flat veya eski iç içe format
    var displayTips: [Tip] {
        if let tips = travelTips, !tips.isEmpty { return tips }
        return aiResults?.rag?.travelTips?.tips ?? []
    }

    /// Transkript — flat string veya iç içe format
    var displayTranscript: String? {
        if let t = transcription, !t.isEmpty { return t }
        return aiResults?.audio?.transcription?.transcript
    }

    /// OCR POI listesi
    var displayOcrPois: [String] {
        if let p = ocrPois, !p.isEmpty { return p }
        return aiResults?.ocrPois ?? []
    }
}

// ── Mobile BFF Flat Modeller ────────────────────────────────────────────────

struct MobileLocation: Codable {
    let index: Int
    let name: String
    let type: String?
    let latitude: Double
    let longitude: Double
    let importance: Double?
}

struct RoutePoint: Codable {
    let latitude: Double
    let longitude: Double
    let name: String
}

struct AIResults: Codable {
    let ocr: OCRResults?
    let ner: NERResults?
    let rag: RAGResults?
    let nominatim: NominatimResults?
    let audio: AudioResults?
    let processingTime: Double?
    let detections: DetectionResults?
    let ocrPois: [String]?

    enum CodingKeys: String, CodingKey {
        case ocr, ner, rag, nominatim, audio
        case processingTime = "processing_time"
        case ocrPois = "ocr_pois"
        case detections
    }
}

struct NominatimResults: Codable {
    let deduplicatedLocations: [EnrichedLocation]?
    
    enum CodingKeys: String, CodingKey {
        case deduplicatedLocations = "deduplicated_locations"
    }
}

struct EnrichedLocation: Codable {
    let originalName: String
    let placeData: PlaceData?
    
    enum CodingKeys: String, CodingKey {
        case originalName = "original_name"
        case placeData = "place_data"
    }
}

struct PlaceData: Codable {
    let name: String?
    let type: String?
    let category: String?       // Müze, Kafe, Tarihi Alan…
    let importance: Double?
    let location: LocationCoordinate?
}

struct LocationCoordinate: Codable {
    let lat: Double
    let lng: Double
}

struct DetectionResults: Codable {
    let count: Int?
    let topObjects: [String: Int]?
    enum CodingKeys: String, CodingKey {
        case count
        case topObjects = "top_objects"
    }
}

struct AudioResults: Codable {
    let transcription: TranscriptionResult?
}

struct TranscriptionResult: Codable {
    let transcript: String?
    let language: String?
}

struct OCRResults: Codable {
    let extractedTexts: [String]?
    enum CodingKeys: String, CodingKey {
        case extractedTexts = "extracted_texts"
    }
}

struct NERResults: Codable {
    let extractedLocations: [String]?
    enum CodingKeys: String, CodingKey {
        case extractedLocations = "extracted_locations"
    }
}

struct RAGResults: Codable {
    let travelTips: TravelTips?
    enum CodingKeys: String, CodingKey {
        case travelTips = "travel_tips"
    }
}

struct TravelTips: Codable {
    let tips: [Tip]?
    let summary: String?
}

struct Tip: Codable {
    let location: String
    let tip: String
}
