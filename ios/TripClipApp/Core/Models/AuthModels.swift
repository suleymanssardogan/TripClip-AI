import Foundation

struct AuthResponse: Decodable {
    let accessToken:  String
    let refreshToken: String
    let userId:       Int
    let email:        String
    let tokenType:    String?
}

struct AuthUser: Codable {
    let id:    Int
    let email: String
    let token: String
}

/// `{"status": "ok"}` gibi minimal yanıtlar için — alanları önemsemeyen çağrılar
/// (örn. logout) bu tipi kullanır.
struct StatusResponse: Decodable {
    let status: String?
}
