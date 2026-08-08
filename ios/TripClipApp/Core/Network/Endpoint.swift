import Foundation

enum HTTPMethod: String {
    case get    = "GET"
    case post   = "POST"
    case put    = "PUT"
    case patch  = "PATCH"
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
    /// Durak sırası — listede olmayan durak silinmiş sayılır (bkz. mobile-bff
    /// video_transformer._apply_stop_order). `order` gün başına durak id listesi;
    /// mobil tek gün kullanıyor, id'ler LocationPin.index (kalıcı kimlik).
    case updateStopOrder(videoID: Int, order: [[Int]])
    case deletePlan(videoID: Int)

    // Plans
    case publicPlans(city: String?, limit: Int, offset: Int)
    case platformStats

    // Library — videolar-arası, tekilleştirilmiş mekan kütüphanesi
    case library(city: String?, q: String?, limit: Int, offset: Int)
    /// Anlamsal arama — "o sahildeki kafe" tarzı sorgular. Sunucu Qdrant
    /// yapılandırılmamışsa/eşleşme yoksa sessizce substring aramasına düşer,
    /// bu yüzden ayrı bir "bulunamadı" hata durumu ele almaya gerek yok.
    case librarySemanticSearch(q: String, city: String?, category: String?, limit: Int)

    // Trip Builder — Library'den seçilen mekanlardan TSP ile rotalanmış gezi
    case createTrip(title: String, placeIDs: [Int])
    case tripList
    case tripDetail(tripID: Int)
    case updateTripStopOrder(tripID: Int, order: [[Int]])
    case deleteTrip(tripID: Int)

    // AI Trip Optimizer — mevcut bir Trip'in duraklarından çok-günlü, zaman-
    // pencereli bir itinerary üretir (bkz. docs/trip-optimizer-bff.md). Trip
    // Builder'ın kendi TSP rotasını (createTrip) DEĞİŞTİRMEZ — ayrı, kalıcı
    // bir önizleme.
    case optimizeTrip(tripID: Int, placeIDs: [Int])
    case itineraries(tripID: Int)
    case itineraryDetail(itineraryID: Int)

    // Analytics — shared-trip büyüme hunisi (bkz. docs/analytics/shared-trip-events.md)
    case trackAnalyticsEvent(event: String, tripID: Int, source: String)
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
        case .updateStopOrder(let id, _):   return "/api/mobile/videos/\(id)/order"
        case .deletePlan(let id):           return "/api/mobile/videos/\(id)"
        case .publicPlans:                  return "/api/mobile/videos/public"
        case .platformStats:                return "/api/mobile/videos/stats"
        case .library:                      return "/api/mobile/places"
        case .librarySemanticSearch:         return "/api/mobile/places"
        case .createTrip:                   return "/api/mobile/trips"
        case .tripList:                     return "/api/mobile/trips"
        case .tripDetail(let id):           return "/api/mobile/trips/\(id)"
        case .updateTripStopOrder(let id, _): return "/api/mobile/trips/\(id)/order"
        case .deleteTrip(let id):           return "/api/mobile/trips/\(id)"
        case .optimizeTrip(let id, _):      return "/api/mobile/trips/\(id)/optimize"
        case .itineraries(let id):          return "/api/mobile/trips/\(id)/itineraries"
        case .itineraryDetail(let id):      return "/api/mobile/itineraries/\(id)"
        case .trackAnalyticsEvent:          return "/api/mobile/analytics/events"
        }
    }

    var method: HTTPMethod {
        switch self {
        case .login, .register, .appleSignIn, .refresh, .logout, .queueUrl, .createTrip, .optimizeTrip, .trackAnalyticsEvent: return .post
        case .registerDeviceToken: return .put
        case .updateStopOrder, .updateTripStopOrder: return .patch
        case .deletePlan, .deleteTrip: return .delete
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

        case .updateStopOrder(_, let order):
            return ["order": order]

        case .createTrip(let title, let placeIDs):
            return ["title": title, "place_ids": placeIDs]

        case .updateTripStopOrder(_, let order):
            return ["order": order]

        case .optimizeTrip(_, let placeIDs):
            // start_date/duration_days/preferred_*_time/strategy kasıtlı olarak
            // gönderilmiyor — core-api'nin kendi varsayılanları (09:00-18:00,
            // greedy_distance) kullanılır (bkz. OptimizeTripRequest). iOS v1'de
            // bunlar için henüz bir seçim ekranı yok.
            return ["selected_place_ids": placeIDs]

        case .trackAnalyticsEvent(let event, let tripID, let source):
            return ["event": event, "trip_id": tripID, "source": source]

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
        case .library(let city, let q, let limit, let offset):
            var items = [
                URLQueryItem(name: "limit",  value: String(limit)),
                URLQueryItem(name: "offset", value: String(offset)),
            ]
            if let city { items.append(URLQueryItem(name: "city", value: city)) }
            if let q    { items.append(URLQueryItem(name: "q", value: q)) }
            return items
        case .librarySemanticSearch(let q, let city, let category, let limit):
            var items = [
                URLQueryItem(name: "q",        value: q),
                URLQueryItem(name: "semantic", value: "true"),
                URLQueryItem(name: "limit",    value: String(limit)),
            ]
            if let city     { items.append(URLQueryItem(name: "city", value: city)) }
            if let category { items.append(URLQueryItem(name: "category", value: category)) }
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
