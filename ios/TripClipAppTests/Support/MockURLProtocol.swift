import Foundation

/// `URLProtocol` tabanlı ağ mock'u — `APIClientTests`'in gerçek `APIClient`
/// sınıfını (mock DEĞİL) gerçek bir `URLSession` üzerinden, ama hiçbir
/// gerçek ağ çağrısı yapmadan test edebilmesi için. `FakeAPIClient`
/// (`APIClientProtocol` sahte implementasyonu) `APIClient.send`'in KENDİSİNİ
/// —401→refresh→tekrar-dene sarmalayıcısını— hiç çalıştırmaz; bu dosya
/// tam olarak o sarmalayıcıyı gerçek HTTP durum kodlarıyla tetiklemek için
/// var (M35 audit bulgusu: bu sarmalayıcının daha önce hiç doğrudan testi
/// yoktu).
final class MockURLProtocol: URLProtocol {

    /// Her istek için senkron bir handler — istenen (durum kodu, gövde)
    /// çiftini döner. Testler arası sızıntıyı önlemek için her testin
    /// başında/sonunda `nil`'e sıfırlanmalı.
    nonisolated(unsafe) static var requestHandler: ((URLRequest) throws -> (HTTPURLResponse, Data))?

    override class func canInit(with request: URLRequest) -> Bool { true }
    override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }

    override func startLoading() {
        guard let handler = Self.requestHandler else {
            client?.urlProtocol(self, didFailWithError: URLError(.badURL))
            return
        }
        do {
            let (response, data) = try handler(request)
            client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
            client?.urlProtocol(self, didLoad: data)
            client?.urlProtocolDidFinishLoading(self)
        } catch {
            client?.urlProtocol(self, didFailWithError: error)
        }
    }

    override func stopLoading() {}

    static func makeSession() -> URLSession {
        let config = URLSessionConfiguration.ephemeral
        config.protocolClasses = [MockURLProtocol.self]
        return URLSession(configuration: config)
    }
}
