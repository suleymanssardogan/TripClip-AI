import Foundation
import OSLog

// MARK: - Protocol

protocol APIClientProtocol: Sendable {
    func send<T: Decodable>(_ endpoint: Endpoint, token: String?) async throws -> T
}

// MARK: - Live Implementation

// @unchecked Sendable: `refreshHandler` yalnızca AuthEnvironment.init sırasında
// bir kez atanır (main actor), sonrasında salt okunur gibi kullanılır — YOLO
// tarzı bir race koşulu pratikte oluşmaz (aynı desen BackgroundUploader'da da var).
final class APIClient: APIClientProtocol, @unchecked Sendable {

    let baseURL:       URL
    var baseURLString: String { baseURL.absoluteString }

    private let session: URLSession
    private let decoder: JSONDecoder

    /// Access token süresi dolduğunda (401) çağrılır — yeni bir access token
    /// döndürürse istek bir kez tekrarlanır; `nil` dönerse (refresh de başarısız)
    /// orijinal 401 hatası fırlatılır. AuthEnvironment tarafından bağlanır.
    var refreshHandler: (() async -> String?)?

    init(baseURL: URL = Config.apiBaseAsURL,
         session: URLSession = .shared) {
        self.baseURL = baseURL
        self.session = session
        self.decoder = JSONDecoder()
        self.decoder.keyDecodingStrategy = .convertFromSnakeCase
    }

    // MARK: - JSON request

    func send<T: Decodable>(_ endpoint: Endpoint, token: String? = nil) async throws -> T {
        do {
            return try await performSend(endpoint, token: token)
        } catch APIError.unauthorized {
            // Refresh endpoint'inin kendisi 401 dönerse tekrar refresh denemeye
            // kalkışma — sonsuz döngüyü önler, refresh token da geçersizdir.
            if case .refresh = endpoint {
                throw APIError.unauthorized
            }
            guard let refreshHandler, let newToken = await refreshHandler() else {
                throw APIError.unauthorized
            }
            return try await performSend(endpoint, token: newToken)
        }
    }

    private func performSend<T: Decodable>(_ endpoint: Endpoint, token: String?) async throws -> T {
        let request: URLRequest
        do {
            request = try endpoint.urlRequest(baseURL: baseURL, token: token)
        } catch {
            throw APIError.network(error as? URLError ?? URLError(.badURL))
        }

        Logger.network.debug("→ \(request.httpMethod ?? "?") \(request.url?.path() ?? "")")

        let data: Data
        let response: URLResponse

        do {
            (data, response) = try await session.data(for: request)
        } catch let urlError as URLError {
            throw APIError.network(urlError)
        }

        let statusCode = (response as? HTTPURLResponse)?.statusCode ?? 0
        Logger.network.debug("← \(statusCode) \(request.url?.path() ?? "")")

        switch statusCode {
        case 200..<300: break
        case 401: throw APIError.unauthorized
        case 404: throw APIError.notFound
        case 400, 422:
            let envelope = try? decoder.decode(ErrorEnvelope.self, from: data)
            throw APIError.server(
                code:    envelope?.error.code    ?? "ERROR",
                message: envelope?.error.message ?? "Geçersiz istek."
            )
        default:
            let envelope = try? decoder.decode(ErrorEnvelope.self, from: data)
            throw APIError.server(
                code:    envelope?.error.code    ?? "ERROR",
                message: envelope?.error.message ?? "Sunucu hatası (\(statusCode))."
            )
        }

        do {
            return try decoder.decode(T.self, from: data)
        } catch {
            Logger.network.error("Decoding failed: \(error)")
            throw APIError.decoding(error)
        }
    }

    // MARK: - Multipart video upload

    struct UploadResponse: Decodable {
        let id: Int
        let status: String
    }

    func uploadVideoFile(
        data: Data,
        filename: String,
        token: String,
        onProgress: @Sendable @escaping (Double) -> Void
    ) async throws -> UploadResponse {
        let boundary = "TripClip-\(UUID().uuidString)"
        var body = Data()

        body.append("--\(boundary)\r\n".utf8)
        body.append("Content-Disposition: form-data; name=\"file\"; filename=\"\(filename)\"\r\n".utf8)
        body.append("Content-Type: video/mp4\r\n\r\n".utf8)
        body.append(data)
        body.append("\r\n--\(boundary)--\r\n".utf8)

        var request = URLRequest(url: baseURL.appending(path: "/api/mobile/videos/upload"))
        request.httpMethod = "POST"
        request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        request.timeoutInterval = 600

        Logger.upload.info("Uploading \(filename) (\(data.count / 1024)KB)")

        // URLSession with delegate for progress reporting
        let delegate = UploadProgressDelegate(onProgress: onProgress)
        let progressSession = URLSession(configuration: .default, delegate: delegate, delegateQueue: nil)

        let (responseData, response) = try await progressSession.upload(for: request, from: body)

        let statusCode = (response as? HTTPURLResponse)?.statusCode ?? 0
        if statusCode >= 400 {
            let envelope = try? decoder.decode(ErrorEnvelope.self, from: responseData)
            throw APIError.server(
                code:    envelope?.error.code    ?? "ERROR",
                message: envelope?.error.message ?? "Yükleme başarısız (\(statusCode))."
            )
        }

        return try decoder.decode(UploadResponse.self, from: responseData)
    }
}

// MARK: - Upload Progress Delegate

private final class UploadProgressDelegate: NSObject, URLSessionTaskDelegate, @unchecked Sendable {

    private let onProgress: @Sendable (Double) -> Void

    init(onProgress: @Sendable @escaping (Double) -> Void) {
        self.onProgress = onProgress
    }

    func urlSession(
        _ session: URLSession,
        task: URLSessionTask,
        didSendBodyData bytesSent: Int64,
        totalBytesSent: Int64,
        totalBytesExpectedToSend: Int64
    ) {
        guard totalBytesExpectedToSend > 0 else { return }
        onProgress(Double(totalBytesSent) / Double(totalBytesExpectedToSend))
    }
}

// MARK: - Error Envelope

private struct ErrorEnvelope: Decodable {
    struct ErrorBody: Decodable {
        let code: String
        let message: String
    }
    let error: ErrorBody
}

// MARK: - Data helpers

private extension Data {
    mutating func append(_ string: String) {
        if let d = string.data(using: .utf8) { append(d) }
    }
    mutating func append(_ string: String.UTF8View) {
        if let d = String(string).data(using: .utf8) { append(d) }
    }
}

// MARK: - Logger

extension Logger {
    static let network = Logger(subsystem: "com.sardogan.TripClipAI", category: "network")
    static let auth    = Logger(subsystem: "com.sardogan.TripClipAI", category: "auth")
    static let upload  = Logger(subsystem: "com.sardogan.TripClipAI", category: "upload")
}
