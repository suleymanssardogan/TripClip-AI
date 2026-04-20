import Foundation

class APIService {
    static let shared = APIService()
    private let baseURL = "http://127.0.0.1:8001"

    
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
}

// Models
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
    let aiResults: AIResults?
    
    enum CodingKeys: String, CodingKey {
        case id, filename, status, duration
        case aiResults = "ai_results"
    }
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
