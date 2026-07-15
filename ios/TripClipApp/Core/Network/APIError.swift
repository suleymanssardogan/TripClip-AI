import Foundation

enum APIError: LocalizedError {
    case network(URLError)
    case unauthorized
    case notFound
    case server(code: String, message: String)
    case decoding(Error)
    case unknown(statusCode: Int)

    var errorDescription: String? {
        switch self {
        case .network:                        return "Sunucuya ulaşılamıyor. İnternet bağlantınızı kontrol edin."
        case .unauthorized:                   return "Oturum süresi doldu. Lütfen tekrar giriş yapın."
        case .notFound:                       return "İçerik bulunamadı."
        case .server(_, let message):         return message
        case .decoding:                       return "Sunucu yanıtı işlenemedi."
        case .unknown(let code):              return "Beklenmeyen hata (HTTP \(code))."
        }
    }

    var isUnauthorized: Bool {
        if case .unauthorized = self { return true }
        return false
    }
}
