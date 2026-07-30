import Foundation

/// Access token'ın süresini yerel olarak okur.
///
/// Neden gerekli: video yükleme yolu (`APIClient.uploadVideoFile`) ve Share
/// Extension'ın background upload'ı, `APIClient.send`'in 401-yakalayıp-yenileyen
/// sarmalayıcısını kullanmıyor. 30 dakikalık access token dolduğunda yükleme
/// ham bir 401 ile düşüyordu ve kullanıcının tek çıkışı çıkış/giriş yapmaktı.
/// Yüklemeye başlamadan ÖNCE süreyi kontrol edip gerekirse yenilemek, onlarca
/// MB'lık bir gövdeyi boşa göndermekten de iyi.
enum JWT {

    /// Token'ın `exp` claim'ini çözer. İmzayı DOĞRULAMAZ — doğrulama sunucunun
    /// işi; buradaki tek amaç "yenilemeli miyim?" sorusuna cevap vermek.
    static func expiryDate(of token: String) -> Date? {
        let segments = token.split(separator: ".")
        guard segments.count == 3,
              let payload = base64URLDecode(String(segments[1])),
              let json = try? JSONSerialization.jsonObject(with: payload) as? [String: Any],
              let exp = json["exp"] as? TimeInterval
        else { return nil }

        return Date(timeIntervalSince1970: exp)
    }

    /// Token `leeway` saniye içinde dolacaksa (veya süresi okunamıyorsa) true.
    /// Okunamayan token'ı "süresi dolmuş" saymak güvenli taraf: en kötü ihtimalle
    /// gereksiz bir yenileme isteği atılır.
    static func isExpired(_ token: String, leeway: TimeInterval = 300) -> Bool {
        guard let expiry = expiryDate(of: token) else { return true }
        return expiry.timeIntervalSinceNow <= leeway
    }

    // MARK: - Private

    /// JWT base64url kullanır: `+` → `-`, `/` → `_`, padding atılmış.
    private static func base64URLDecode(_ value: String) -> Data? {
        var base64 = value
            .replacingOccurrences(of: "-", with: "+")
            .replacingOccurrences(of: "_", with: "/")

        let remainder = base64.count % 4
        if remainder > 0 {
            base64 += String(repeating: "=", count: 4 - remainder)
        }
        return Data(base64Encoded: base64)
    }
}
