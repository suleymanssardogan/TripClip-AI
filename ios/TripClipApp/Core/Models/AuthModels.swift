import Foundation

struct AuthResponse: Decodable {
    let accessToken: String
    let userId:      Int
    let email:       String
    let tokenType:   String?
}

struct AuthUser: Codable {
    let id:    Int
    let email: String
    let token: String
}
