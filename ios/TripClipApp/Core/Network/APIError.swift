import Foundation

enum APIError: LocalizedError {
    case network(URLError)
    /// 401. `message` sunucunun gönderdiği açıklamadır — giriş ekranında
    /// "E-posta adresi veya şifre hatalı" gibi. Gövdesiz 401'lerde (gerçek
    /// token süre dolumu) nil kalır ve oturum mesajına düşeriz.
    case unauthorized(message: String?)
    case notFound
    case server(code: String, message: String)
    case decoding(Error)
    case unknown(statusCode: Int)

    var errorDescription: String? {
        switch self {
        case .network:                        return "Sunucuya ulaşılamıyor. İnternet bağlantınızı kontrol edin."
        case .unauthorized(let message):      return message ?? "Oturum süresi doldu. Lütfen tekrar giriş yapın."
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
