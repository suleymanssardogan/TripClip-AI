import XCTest
@testable import TripClipApp

/// M35 audit bulgusu: `ProcessingViewModel.fetchProgress()` daha önce TÜM
/// hataları (401 dahil) genel/kalıcı-olmayan bir ağ hatası gibi yutuyor ve
/// polling'i sürdürüyordu — oturum sona erdikten sonra bile `maxWaitSeconds`
/// (300s) boyunca 2 saniyede bir gereksiz yere denemeye devam ediyordu.
/// Diğer TÜM ViewModel'ler (`HomeViewModel`, `TripDetailViewModel` vb.) 401'i
/// hemen durdurur — bu dosya yalnızca o tutarsızlığın regresyon testini içerir.
@MainActor
final class ProcessingViewModelTests: XCTestCase {

    func test_fetchProgress_unauthorized_stopsPollingImmediately() async {
        let fake = FakeAPIClient()
        fake.result = .failure(APIError.unauthorized(message: nil))
        let vm = ProcessingViewModel(videoID: 1, apiClient: fake, token: "expired-token")

        vm.startMonitoring()
        // Gerçek bir zamanlayıcı DEĞİL — yalnızca ilk `fetchProgress()`
        // çağrısının dönüp döngüyü durdurmasını beklemek için kısa bir ara.
        try? await Task.sleep(nanoseconds: 300_000_000)
        vm.stopMonitoring()

        XCTAssertEqual(fake.callCount, 1, "401 sonrası polling HEMEN durmalı, tekrar tekrar denenmemeli")
    }

    /// M37 regression: `APIClient.send`'in kendi refresh'i BAŞARILI olup
    /// (yeni token) tekrarlanan istek YİNE 401 dönerse — nadir ama mümkün
    /// bir uç durum — `AuthEnvironment.handleUnauthorized()` bu ViewModel
    /// için hiç tetiklenmez (yalnızca refresh'in KENDİSİ başarısız olursa
    /// çağrılır). Önceden bu, ekranı SONSUZA DEK donmuş bırakıyordu — görevler
    /// iptal ama `stage` hiçbir zaman terminal bir değere geçmiyordu, ne
    /// hata mesajı ne de geri dönüş CTA'sı gösteriliyordu. Artık her zaman
    /// kendi `.failed` durumuna geçiyor.
    func test_fetchProgress_unauthorized_setsTerminalFailedStage() async {
        let fake = FakeAPIClient()
        fake.result = .failure(APIError.unauthorized(message: nil))
        let vm = ProcessingViewModel(videoID: 1, apiClient: fake, token: "expired-token")

        vm.startMonitoring()
        try? await Task.sleep(nanoseconds: 300_000_000)
        vm.stopMonitoring()

        guard case .failed = vm.stage else {
            XCTFail("401 sonrası `stage` terminal bir `.failed` olmalı, ekran donmuş kalmamalı — gerçek: \(vm.stage)")
            return
        }
    }

    /// M39 audit bulgusu: bir 404 (video başka bir cihazdan/ekrandan
    /// silinmiş — aynı hesap birden fazla cihazda oturum açabilir) önceden
    /// genel/kalıcı-olmayan bir ağ hatası gibi yutuluyor ve polling
    /// SÜRDÜRÜLÜYORDU; kullanıcı 300s'lik istemci zaman aşımına kadar
    /// "işleniyor, biraz bekleyin" görüyor, ardından "Beklemeye Devam Et"
    /// ile var olmayan bir videoyu YENİDEN 5 dakika daha poll'layabiliyordu.
    /// 404 KALICIDIR — artık polling'i hemen durdurup net bir mesajla
    /// terminal `.failed` durumuna geçiyor.
    func test_fetchProgress_notFound_stopsPollingImmediatelyWithClearMessage() async {
        let fake = FakeAPIClient()
        fake.result = .failure(APIError.notFound)
        let vm = ProcessingViewModel(videoID: 1, apiClient: fake, token: "token")

        vm.startMonitoring()
        try? await Task.sleep(nanoseconds: 300_000_000)
        vm.stopMonitoring()

        XCTAssertEqual(fake.callCount, 1, "404 sonrası polling HEMEN durmalı, tekrar tekrar denenmemeli")
        guard case .failed(let message) = vm.stage else {
            XCTFail("404 sonrası `stage` terminal bir `.failed` olmalı — gerçek: \(vm.stage)")
            return
        }
        XCTAssertEqual(message, "Bu video artık mevcut değil.")
    }
}
