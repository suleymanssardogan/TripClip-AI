import XCTest
@testable import TripClipApp

/// `TripDetailViewModel`in daha önce hiç testi yoktu (`TripDetailModelTests.swift`
/// yalnızca JSON decode testleri içerir). M36, `deleteTrip`in başarısızlık
/// yolunun (`deleteError`/`isDeleting`) `TripDetailView`e HİÇ bağlanmadığını
/// buldu — bir gezi silme isteği başarısız olduğunda hiçbir geri bildirim
/// yoktu. Bu dosya o düzeltmenin dayandığı VM sözleşmesini sabitliyor.
@MainActor
final class TripDetailViewModelTests: XCTestCase {

    private func makeAuth(fake: FakeAPIClient, withUser: Bool = true) -> AuthEnvironment {
        let auth = AuthEnvironment(apiClient: fake)
        if withUser {
            auth.setUserForTesting(AuthUser(id: 1, email: "gezgin@test.com", token: "test-token"))
        }
        return auth
    }

    // MARK: - Initial state

    func test_initialState_isNotDeleting_hasNoDeleteError() {
        let vm = TripDetailViewModel()
        XCTAssertFalse(vm.isDeleting)
        XCTAssertNil(vm.deleteError)
    }

    // MARK: - load() stale-trip handling on 404 (M39)

    /// M39 audit bulgusu: trip başka bir ekrandan/cihazdan silinmişse (aynı
    /// hesap birden fazla cihazda oturum açabilir), `load()` başarısız
    /// olduğunda eski `trip` değerini SESSİZCE tutmaya devam ediyordu — harita/
    /// durak listesi/toolbar aksiyonları hiçbir hata görünmeden artık var
    /// olmayan bir gezi üzerinde etkileşimli kalıyordu. 404'te artık `trip`
    /// temizleniyor, `TripDetailView`in kendi `vm.trip == nil` hata dalı devreye girer.
    func test_load_notFound_clearsStaleTrip() async {
        let fake = FakeAPIClient()
        let auth = makeAuth(fake: fake)
        let vm = TripDetailViewModel()
        await vm.load(tripID: 1, auth: auth, preloaded: TripDetail(id: 1, title: "Test Gezisi", totalDistanceKm: nil, createdAt: nil, stopsCount: 0, days: [], appliedItineraryId: nil, itineraryAppliedAt: nil))
        XCTAssertNotNil(vm.trip)

        fake.result = .failure(APIError.notFound)
        await vm.load(tripID: 1, auth: auth)

        XCTAssertNil(vm.trip, "Trip başka bir yerden silinmişse eski/hayalet veri EKRANDA KALMAMALI")
        XCTAssertNotNil(vm.error)
    }

    /// AYNI değişikliğin ters yönü: GEÇİCİ (404 olmayan) bir hata eski
    /// `trip`i SİLMEMELİ — aksi halde bir ağ blip'i, tıpkı düzeltme öncesi
    /// gerçek silinme senaryosu gibi ekranı gereksiz yere boşaltırdı.
    func test_load_transientError_preservesStaleTrip() async {
        let fake = FakeAPIClient()
        let auth = makeAuth(fake: fake)
        let vm = TripDetailViewModel()
        await vm.load(tripID: 1, auth: auth, preloaded: TripDetail(id: 1, title: "Test Gezisi", totalDistanceKm: nil, createdAt: nil, stopsCount: 0, days: [], appliedItineraryId: nil, itineraryAppliedAt: nil))
        XCTAssertNotNil(vm.trip)

        fake.result = .failure(APIError.server(code: "DATABASE_ERROR", message: "Sunucu geçici olarak kullanılamıyor."))
        await vm.load(tripID: 1, auth: auth)

        XCTAssertNotNil(vm.trip, "Geçici bir hata eski veriyi KORUMALI — yalnızca 404'te temizlenir")
        XCTAssertNotNil(vm.error)
    }

    // MARK: - deleteStop/moveStops failure recovery (M39)

    /// M39 audit bulgusu: `persistDay` beklerken paralel bir mutasyon
    /// (optimizer apply, pull-to-refresh, vb.) sunucu durumunu zaten
    /// değiştirmiş olabilir. Düzenleme başarısız olduğunda eski (düzenleme
    /// ÖNCESİ) yerel `snapshot`'a körü körüne dönmek, o GÜNCEL sunucu
    /// durumunu sessizce EZERdi. Artık başarısızlıkta sunucudan TAZE veri
    /// çekiliyor — bu test, o taze veriyi (eski snapshot'ı DEĞİL) yansıttığını doğrular.
    func test_deleteStop_failure_refetchesFromServer_insteadOfRestoringStaleSnapshot() async {
        let fake = FakeAPIClient()
        let auth = makeAuth(fake: fake)
        let vm = TripDetailViewModel()
        let stop = TripStop(placeId: 1, name: "Yer 1", latitude: 0, longitude: 0, city: nil, category: nil, dayIndex: 0, orderIndex: 0)
        let originalTrip = TripDetail(id: 1, title: "Eski Başlık", totalDistanceKm: nil, createdAt: nil, stopsCount: 1, days: [[stop]], appliedItineraryId: nil, itineraryAppliedAt: nil)
        await vm.load(tripID: 1, auth: auth, preloaded: originalTrip)

        // Sanki bu istek beklerken paralel bir mutasyon zaten sunucudaki
        // trip'i değiştirmiş gibi — başlık FARKLI, bu "taze çekilen" veriyi
        // eski snapshot'tan ayırt etmek için kasıtlı.
        let serverTruthAfterConcurrentChange = TripDetail(id: 1, title: "Sunucudaki Güncel Başlık", totalDistanceKm: nil, createdAt: nil, stopsCount: 1, days: [[stop]], appliedItineraryId: nil, itineraryAppliedAt: nil)
        fake.results = [
            .failure(APIError.server(code: "DATABASE_ERROR", message: "Sunucu geçici olarak kullanılamıyor.")),
            .success(serverTruthAfterConcurrentChange),
        ]

        await vm.deleteStop(stop, auth: auth)

        XCTAssertEqual(vm.trip?.title, "Sunucudaki Güncel Başlık", "Başarısızlık sonrası eski snapshot'a DEĞİL, sunucudan TAZE çekilen veriye dönülmeli")
        XCTAssertNotNil(vm.stopEditError)
    }

    // MARK: - refreshItineraryHistoryFlag / refreshApplyHistoryFlag unauthorized handling (M37)

    /// M37 regression: `preloaded:` ile açılan bir `TripDetailView`de
    /// (bkz. `LibraryView`'ın "Gezi Oluştur" sonrası akışı) `load()` hiç ağa
    /// gitmez — bu iki best-effort bayrak yenileme çağrısı o durumda
    /// ekrandaki TEK gerçek istek olabilir. Önceden 401 dahil HER hatayı
    /// sessizce yutuyorlardı; artık diğer tüm authenticated çağrılarla
    /// AYNI şekilde `isUnauthorized`i kontrol edip oturumu kapatıyorlar.
    func test_refreshItineraryHistoryFlag_unauthorized_logsOut() async {
        let fake = FakeAPIClient()
        fake.result = .failure(APIError.unauthorized(message: nil))
        let auth = makeAuth(fake: fake)
        let vm = TripDetailViewModel()

        await vm.refreshItineraryHistoryFlag(tripID: 1, auth: auth)

        XCTAssertFalse(auth.isAuthenticated)
        XCTAssertFalse(vm.hasItineraryHistory)
    }

    func test_refreshItineraryHistoryFlag_otherError_staysBestEffort() async {
        let fake = FakeAPIClient()
        fake.result = .failure(APIError.server(code: "DATABASE_ERROR", message: "Sunucu geçici olarak kullanılamıyor."))
        let auth = makeAuth(fake: fake)
        let vm = TripDetailViewModel()

        await vm.refreshItineraryHistoryFlag(tripID: 1, auth: auth)

        XCTAssertTrue(auth.isAuthenticated, "401 DIŞINDAKİ hatalar oturumu kapatmamalı — bu hâlâ best-effort")
        XCTAssertFalse(vm.hasItineraryHistory)
    }

    func test_refreshApplyHistoryFlag_unauthorized_logsOut() async {
        let fake = FakeAPIClient()
        fake.result = .failure(APIError.unauthorized(message: nil))
        let auth = makeAuth(fake: fake)
        let vm = TripDetailViewModel()

        await vm.refreshApplyHistoryFlag(tripID: 1, auth: auth)

        XCTAssertFalse(auth.isAuthenticated)
        XCTAssertFalse(vm.hasApplyHistory)
    }

    // MARK: - deleteTrip

    func test_deleteTrip_noTripLoaded_returnsFalse_neverCallsAPI() async {
        let fake = FakeAPIClient()
        let auth = makeAuth(fake: fake)
        let vm = TripDetailViewModel()

        let success = await vm.deleteTrip(auth: auth)

        XCTAssertFalse(success)
        XCTAssertEqual(fake.callCount, 0)
    }

    func test_deleteTrip_success_returnsTrue_clearsDeleteError() async {
        let fake = FakeAPIClient()
        fake.result = .success(SuccessResponse(success: true))
        let auth = makeAuth(fake: fake)
        let vm = TripDetailViewModel()
        await vm.load(tripID: 1, auth: auth, preloaded: TripDetail(id: 1, title: "Test Gezisi", totalDistanceKm: nil, createdAt: nil, stopsCount: 0, days: [], appliedItineraryId: nil, itineraryAppliedAt: nil))

        let success = await vm.deleteTrip(auth: auth)

        XCTAssertTrue(success)
        XCTAssertNil(vm.deleteError)
        XCTAssertFalse(vm.isDeleting)
    }

    /// M36 regression: bu daha önce `TripDetailView`e hiç bağlanmıyordu —
    /// yalnızca VM sözleşmesini sabitliyor (View seviyesindeki alert
    /// bağlantısının kendisi bu proje test target'ında doğrudan test
    /// edilemiyor — bkz. docs/ios-product-audit.md).
    func test_deleteTrip_failure_returnsFalse_setsDeleteError() async {
        let fake = FakeAPIClient()
        fake.result = .failure(APIError.server(code: "DATABASE_ERROR", message: "Sunucu geçici olarak kullanılamıyor."))
        let auth = makeAuth(fake: fake)
        let vm = TripDetailViewModel()
        await vm.load(tripID: 1, auth: auth, preloaded: TripDetail(id: 1, title: "Test Gezisi", totalDistanceKm: nil, createdAt: nil, stopsCount: 0, days: [], appliedItineraryId: nil, itineraryAppliedAt: nil))

        let success = await vm.deleteTrip(auth: auth)

        XCTAssertFalse(success)
        XCTAssertNotNil(vm.deleteError)
        XCTAssertFalse(vm.isDeleting)
    }

    func test_deleteTrip_unauthorized_logsOutAndDoesNotSetDeleteError() async {
        let fake = FakeAPIClient()
        fake.result = .failure(APIError.unauthorized(message: nil))
        let auth = makeAuth(fake: fake)
        let vm = TripDetailViewModel()
        await vm.load(tripID: 1, auth: auth, preloaded: TripDetail(id: 1, title: "Test Gezisi", totalDistanceKm: nil, createdAt: nil, stopsCount: 0, days: [], appliedItineraryId: nil, itineraryAppliedAt: nil))

        let success = await vm.deleteTrip(auth: auth)

        XCTAssertFalse(success)
        XCTAssertFalse(auth.isAuthenticated)
        XCTAssertNil(vm.deleteError)
    }

    func test_deleteTrip_reentrancyGuard_ignoresSecondCallWhileFirstInFlight() async {
        let fake = FakeAPIClient()
        fake.result = .success(SuccessResponse(success: true))
        let started = AsyncGate()
        let proceed = AsyncGate()
        fake.startedGate = started
        fake.gate = proceed
        let auth = makeAuth(fake: fake)
        let vm = TripDetailViewModel()
        await vm.load(tripID: 1, auth: auth, preloaded: TripDetail(id: 1, title: "Test Gezisi", totalDistanceKm: nil, createdAt: nil, stopsCount: 0, days: [], appliedItineraryId: nil, itineraryAppliedAt: nil))

        let first = Task { await vm.deleteTrip(auth: auth) }
        await started.wait()
        XCTAssertTrue(vm.isDeleting)

        let secondResult = await vm.deleteTrip(auth: auth)
        XCTAssertFalse(secondResult, "İkinci silme çağrısı devam eden silme sırasında yoksayılmalı")

        await proceed.open()
        _ = await first.value
        XCTAssertEqual(fake.callCount, 1)
    }
}
