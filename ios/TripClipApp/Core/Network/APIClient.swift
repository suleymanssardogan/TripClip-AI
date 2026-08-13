import Foundation
import OSLog

// MARK: - Protocol

protocol APIClientProtocol: Sendable {
    func send<T: Decodable>(_ endpoint: Endpoint, token: String?) async throws -> T
    func uploadVideoFile(
        data: Data, filename: String, token: String,
        onProgress: @Sendable @escaping (Double) -> Void
    ) async throws -> APIClient.UploadResponse
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
        } catch APIError.unauthorized(let message) {
            // token: nil ile çağrılan (henüz oturum açılmamış) uç noktalar
            // ASLA refresh denemesine girmemeli — 401'leri süresi dolmuş bir
            // oturumla değil, kendi alan-özgü nedenleriyle ilgilidir (ör.
            // Google girişinde GOOGLE_EMAIL_NOT_VERIFIED, şifre sıfırlamada
            // PASSWORD_RESET_TOKEN_EXPIRED — mobile-bff error_wrapper.py'nin
            // tamamı 401'e eşliyor). Buraya girip gereksiz bir refresh
            // denemesi (ve varsa GERÇEKTEN giriş yapılmış, alakasız bir
            // oturumun yan etki olarak yenilenmesi/logout edilmesi) ASLA
            // olmamalı (M35 audit bulgusu). `.refresh`'in kendisi ayrıca
            // sonsuz döngüyü önlemek için hariç tutulur.
            switch endpoint {
            case .refresh, .login, .register, .appleSignIn, .googleSignIn, .forgotPassword, .resetPassword:
                throw APIError.unauthorized(message: message)
            default:
                break
            }
            guard let refreshHandler, let newToken = await refreshHandler() else {
                throw APIError.unauthorized(message: message)
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
        case 401:
            // Sunucu mesajını taşı — core-api hatalı giriş için zaten
            // "E-posta adresi veya şifre hatalı" döndürüyor.
            let envelope = try? decoder.decode(ErrorEnvelope.self, from: data)
            throw APIError.unauthorized(message: envelope?.message)
        case 404: throw APIError.notFound
        case 400, 422:
            let envelope = try? decoder.decode(ErrorEnvelope.self, from: data)
            throw APIError.server(
                code:    envelope?.code    ?? "ERROR",
                message: envelope?.message ?? "Geçersiz istek."
            )
        default:
            let envelope = try? decoder.decode(ErrorEnvelope.self, from: data)
            throw APIError.server(
                code:    envelope?.code    ?? "ERROR",
                message: envelope?.message ?? "Sunucu hatası (\(statusCode))."
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
            // 401'i ayrı tut: çağıran taraf oturumu tazeleyip tekrar deneyebilsin,
            // kullanıcı da ham "(401)" yerine anlamlı bir mesaj görsün.
            if statusCode == 401 {
                throw APIError.unauthorized(message: envelope?.message)
            }
            throw APIError.server(
                code:    envelope?.code    ?? "ERROR",
                message: envelope?.message ?? "Yükleme başarısız (\(statusCode))."
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

/// Sunucu hata gövdesi — iki farklı şekli de kabul eder.
///
/// core-api ve web-bff dokümantasyondaki zarfı kullanıyor:
///     {"error": {"code": "...", "message": "..."}}
/// mobile-bff ise düz gönderiyor:
///     {"code": "...", "message": "..."}
///
/// Eskiden yalnızca zarf çözülüyordu, dolayısıyla mobil taraftaki HİÇBİR sunucu
/// mesajı okunamıyor ve kullanıcı hep jenerik metin görüyordu ("Oturum süresi
/// doldu", "Geçersiz istek"). İki şekli de desteklemek, BFF hizalanana kadar
/// (ve sonrasında da) doğru mesajı göstermenin en güvenli yolu.
private struct ErrorEnvelope: Decodable {
    let code: String
    let message: String

    private enum CodingKeys: String, CodingKey {
        case error, code, message
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)

        let source: KeyedDecodingContainer<CodingKeys>
        if let nested = try? container.nestedContainer(keyedBy: CodingKeys.self, forKey: .error) {
            source = nested
        } else {
            source = container
        }

        guard let message = try? source.decode(String.self, forKey: .message) else {
            throw DecodingError.keyNotFound(
                CodingKeys.message,
                .init(codingPath: decoder.codingPath, debugDescription: "Hata gövdesinde message yok")
            )
        }
        self.message = message
        self.code    = (try? source.decode(String.self, forKey: .code)) ?? "ERROR"
    }
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
