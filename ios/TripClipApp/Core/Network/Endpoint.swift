import Foundation

enum HTTPMethod: String {
    case get    = "GET"
    case post   = "POST"
    case put    = "PUT"
    case delete = "DELETE"
}

enum Endpoint {

    // Auth
    case login(email: String, password: String)
    case register(email: String, password: String, username: String?)
    case appleSignIn(identityToken: String, fullName: String?)
    case refresh(refreshToken: String)
    case logout(refreshToken: String)
    case registerDeviceToken(token: String)

    // Videos
    case userVideos(userID: Int)
    case videoDetail(videoID: Int)
    case videoProgress(videoID: Int)
    case queueUrl(url: String)

    // Plans
    case publicPlans(city: String?, limit: Int, offset: Int)
    case platformStats
}

extension Endpoint {

    var path: String {
        switch self {
        case .login:                        return "/api/mobile/auth/login"
        case .register:                     return "/api/mobile/auth/register"
        case .appleSignIn:                  return "/api/mobile/auth/apple"
        case .refresh:                      return "/api/mobile/auth/refresh"
        case .logout:                       return "/api/mobile/auth/logout"
        case .registerDeviceToken:          return "/api/mobile/auth/device-token"
        case .userVideos:                   return "/api/mobile/videos"
        case .videoDetail(let id):          return "/api/mobile/videos/\(id)"
        case .videoProgress(let id):        return "/api/mobile/videos/\(id)/progress"
        case .queueUrl:                     return "/api/mobile/videos/queue-url"
        case .publicPlans:                  return "/api/mobile/videos/public"
        case .platformStats:                return "/api/mobile/videos/stats"
        }
    }

    var method: HTTPMethod {
        switch self {
        case .login, .register, .appleSignIn, .refresh, .logout, .queueUrl: return .post
        case .registerDeviceToken: return .put
        default: return .get
        }
    }

    var body: [String: Any]? {
        switch self {
        case .login(let email, let password):
            return ["email": email, "password": password]

        case .register(let email, let password, let username):
            var b: [String: Any] = ["email": email, "password": password]
            if let username { b["username"] = username }
            return b

        case .appleSignIn(let token, let name):
            var b: [String: Any] = ["identity_token": token]
            if let name { b["full_name"] = name }
            return b

        case .queueUrl(let url):
            return ["url": url, "source": "ios_app"]

        case .refresh(let refreshToken), .logout(let refreshToken):
            return ["refresh_token": refreshToken]

        case .registerDeviceToken(let token):
            return ["token": token]

        default:
            return nil
        }
    }

    var queryItems: [URLQueryItem]? {
        switch self {
        case .publicPlans(let city, let limit, let offset):
            var items = [
                URLQueryItem(name: "limit",  value: String(limit)),
                URLQueryItem(name: "offset", value: String(offset)),
            ]
            if let city { items.append(URLQueryItem(name: "city", value: city)) }
            return items
        default:
            return nil
        }
    }

    func urlRequest(baseURL: URL, token: String?) throws -> URLRequest {
        var components = URLComponents(
            url: baseURL.appendingPathComponent(path),
            resolvingAgainstBaseURL: false
        )!
        components.queryItems = queryItems

        guard let url = components.url else {
            throw URLError(.badURL)
        }

        var request = URLRequest(url: url, timeoutInterval: 30)
        request.httpMethod = method.rawValue
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        if let token {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }

        if let body {
            request.httpBody = try JSONSerialization.data(withJSONObject: body)
        }

        return request
    }
}
