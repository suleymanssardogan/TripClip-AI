import Foundation
@testable import TripClipApp

/// `APIClientProtocol` test double — gerçek ağ çağrısı yapmaz, önceden
/// kaydedilmiş bir sonuç/hata döndürür. `gate` verilirse `send` onu
/// tamamlanana kadar askıda kalır — `isLoading` gibi ara durumları
/// deterministik biçimde gözlemlemek için (bkz. AsyncGate).
///
/// `startedGate` verilirse, `send` içine gerçekten girildiği an (herhangi bir
/// `await`'ten ÖNCE, `callCount` artışıyla aynı anda) açılır — testin
/// `Task.yield()` sayısına/zamanlamaya güvenerek "çağrı başladı mı" tahmin
/// etmesi yerine bunu kesin biçimde beklemesini sağlar. `Task.yield()` tabanlı
/// ilk sürüm sistem yükü altında (paralel xcodebuild çalıştırmaları vb.)
/// gözlemlenebilir biçimde kırılgan çıktı — bu yüzden değiştirildi.
final class FakeAPIClient: APIClientProtocol, @unchecked Sendable {

    var result: Result<Any, Error> = .failure(APIError.unknown(statusCode: 0))
    /// Ard arda gelen ÇAĞRILARA FARKLI sonuçlar vermek gerektiğinde (ör.
    /// "ilk istek başarısız, ardından tetiklenen bir yeniden-çekme farklı
    /// bir gövdeyle başarılı" — M39 `restoreAfterFailedStopEdit` testi)
    /// doldurulur; her `send()` çağrısı burada bir eleman varsa onu POP'lar
    /// (sırayla tüketir), boşsa tek/statik `result`'a düşer. Var olan tüm
    /// testler `results`'ı hiç ayarlamadığı için davranışları DEĞİŞMEZ.
    var results: [Result<Any, Error>] = []
    var gate: AsyncGate?
    var startedGate: AsyncGate?

    private(set) var callCount = 0
    private(set) var lastEndpoint: Endpoint?
    private(set) var lastToken: String?

    func send<T: Decodable>(_ endpoint: Endpoint, token: String?) async throws -> T {
        callCount += 1
        lastEndpoint = endpoint
        lastToken = token

        if let startedGate { await startedGate.open() }
        if let gate { await gate.wait() }

        let result = results.isEmpty ? self.result : results.removeFirst()
        switch result {
        case .success(let value):
            guard let typed = value as? T else {
                fatalError("FakeAPIClient: kayıtlı sonuç \(T.self) tipine dönüştürülemedi (gerçek tip: \(type(of: value)))")
            }
            return typed
        case .failure(let error):
            throw error
        }
    }

    func uploadVideoFile(
        data: Data, filename: String, token: String,
        onProgress: @Sendable @escaping (Double) -> Void
    ) async throws -> APIClient.UploadResponse {
        fatalError("FakeAPIClient: uploadVideoFile bu test paketinde kullanılmıyor")
    }
}

/// Bir async çağrının belirli bir noktada askıda kalmasını (ve testin
/// istediği anda serbest bırakmasını) sağlayan basit bir kapı — Swift'in
/// yapılandırılmış eşzamanlılığında "isLoading tam da istek sürerken true
/// mu" gibi ara-durum testleri için standart bir desen.
actor AsyncGate {
    private var isOpen = false
    private var continuation: CheckedContinuation<Void, Never>?

    func wait() async {
        if isOpen { return }
        await withCheckedContinuation { continuation = $0 }
    }

    func open() {
        isOpen = true
        continuation?.resume()
        continuation = nil
    }
}
