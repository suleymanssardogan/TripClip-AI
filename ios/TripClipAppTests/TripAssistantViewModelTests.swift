import XCTest
@testable import TripClipApp

@MainActor
final class TripAssistantViewModelTests: XCTestCase {

    private func makeAuth(fake: FakeAPIClient, withUser: Bool = true) -> AuthEnvironment {
        let auth = AuthEnvironment(apiClient: fake)
        if withUser {
            auth.setUserForTesting(AuthUser(id: 1, email: "gezgin@test.com", token: "test-token"))
        }
        return auth
    }

    // MARK: - Initial state

    func test_initialState_isEmpty_notSending_hasNoError() {
        let vm = TripAssistantViewModel()
        XCTAssertTrue(vm.messages.isEmpty)
        XCTAssertFalse(vm.sending)
        XCTAssertNil(vm.sendError)
    }

    /// M35 regression: `TripAssistantView` previously owned its ViewModel as
    /// `@State private var vm = TripAssistantViewModel()` — dismissing the
    /// view (reference-chip tap → back to Trip Detail) and reopening it made
    /// SwiftUI re-evaluate the `NavigationLink` destination, constructing a
    /// BRAND NEW `TripAssistantViewModel()` and silently discarding the whole
    /// conversation. The fix is that `TripDetailView` now owns a single
    /// `@State private var assistantVM` and passes the SAME instance into
    /// `TripAssistantView(vm:)` every time. This test can't drive SwiftUI's
    /// navigation lifecycle directly (no UI test target in this project), but
    /// it pins down the assumption the fix depends on: `TripAssistantViewModel`
    /// is a reference type whose `messages` survive being held by a second,
    /// independent reference — i.e. simply re-passing the SAME instance into
    /// a freshly-constructed `TripAssistantView` (as `TripDetailView` now does)
    /// can never lose state, whereas constructing a NEW instance always would.
    func test_sameInstanceHeldAcrossTwoReferences_preservesConversation() async {
        let fake = FakeAPIClient()
        fake.result = .success(AssistantResponse(answer: "Cevap", references: []))
        let auth = makeAuth(fake: fake)
        let vm = TripAssistantViewModel()

        await vm.send("İlk soru", tripID: 2, auth: auth)
        XCTAssertEqual(vm.messages.count, 2)

        // `TripDetailView`'ın `assistantVM`'i tekrar okuyup `TripAssistantView`'a
        // yeniden geçirmesini simüle eder — YENİ bir ViewModel DEĞİL, AYNI referans.
        let sameInstanceViaSecondReference = vm
        XCTAssertEqual(sameInstanceViaSecondReference.messages.count, 2)
        XCTAssertEqual(sameInstanceViaSecondReference.messages.first?.content, "İlk soru")
    }

    // MARK: - Send (happy path)

    func test_send_appendsUserThenAssistantMessage() async {
        let fake = FakeAPIClient()
        fake.result = .success(AssistantResponse(answer: "Bugün Ayasofya'ya gideceksin.", references: []))
        let auth = makeAuth(fake: fake)
        let vm = TripAssistantViewModel()

        await vm.send("Bugün nereye gideceğim?", tripID: 2, auth: auth)

        XCTAssertEqual(vm.messages.count, 2)
        XCTAssertEqual(vm.messages[0].role, .user)
        XCTAssertEqual(vm.messages[0].content, "Bugün nereye gideceğim?")
        XCTAssertEqual(vm.messages[1].role, .assistant)
        XCTAssertEqual(vm.messages[1].content, "Bugün Ayasofya'ya gideceksin.")
        XCTAssertFalse(vm.sending)
        XCTAssertNil(vm.sendError)
    }

    func test_send_callsAssistantEndpoint_withTripIDAndMessage() async {
        let fake = FakeAPIClient()
        fake.result = .success(AssistantResponse(answer: "Cevap", references: []))
        let auth = makeAuth(fake: fake)
        let vm = TripAssistantViewModel()

        await vm.send("soru", tripID: 42, auth: auth)

        guard case .assistant(let tripID, let message, _) = fake.lastEndpoint else {
            XCTFail("Beklenmeyen endpoint: \(String(describing: fake.lastEndpoint))")
            return
        }
        XCTAssertEqual(tripID, 42)
        XCTAssertEqual(message, "soru")
    }

    func test_send_carriesReferences_fromResponse() async {
        let fake = FakeAPIClient()
        fake.result = .success(AssistantResponse(
            answer: "İlk durağın Ayasofya.",
            references: [AssistantReference(type: "stop", dayIndex: 0, placeId: 25)]
        ))
        let auth = makeAuth(fake: fake)
        let vm = TripAssistantViewModel()

        await vm.send("İlk durağım ne?", tripID: 2, auth: auth)

        XCTAssertEqual(vm.messages.last?.references, [AssistantReference(type: "stop", dayIndex: 0, placeId: 25)])
    }

    // MARK: - Validation / re-entrancy

    func test_send_emptyOrWhitespaceMessage_neverCallsAPI() async {
        let fake = FakeAPIClient()
        let auth = makeAuth(fake: fake)
        let vm = TripAssistantViewModel()

        await vm.send("   ", tripID: 2, auth: auth)

        XCTAssertEqual(fake.callCount, 0)
        XCTAssertTrue(vm.messages.isEmpty)
    }

    func test_send_reentrancyGuard_ignoresSecondSendWhileFirstInFlight() async {
        let fake = FakeAPIClient()
        fake.result = .success(AssistantResponse(answer: "Cevap", references: []))
        let started = AsyncGate()
        let proceed = AsyncGate()
        fake.startedGate = started
        fake.gate = proceed
        let auth = makeAuth(fake: fake)
        let vm = TripAssistantViewModel()

        let first = Task { await vm.send("ilk soru", tripID: 2, auth: auth) }
        await started.wait()
        XCTAssertTrue(vm.sending)

        await vm.send("ikinci soru", tripID: 2, auth: auth)
        XCTAssertEqual(fake.callCount, 1, "İkinci gönderim ağa hiç gitmemeli")

        await proceed.open()
        await first.value
        XCTAssertEqual(fake.callCount, 1)
    }

    func test_send_noToken_neverCallsAPI_andNeverAppendsAStuckMessage() async {
        let fake = FakeAPIClient()
        fake.result = .success(AssistantResponse(answer: "Cevap", references: []))
        let auth = makeAuth(fake: fake, withUser: false)
        let vm = TripAssistantViewModel()

        await vm.send("soru", tripID: 2, auth: auth)

        XCTAssertEqual(fake.callCount, 0)
        XCTAssertTrue(vm.messages.isEmpty, "Token yoksa mesaj sohbette TAKILI kalmamalı")
    }

    // MARK: - Failure handling

    func test_send_failure_removesOptimisticUserMessage_setsError() async {
        let fake = FakeAPIClient()
        fake.result = .failure(APIError.server(code: "ASSISTANT_UNAVAILABLE", message: "AI asistanı şu anda kullanılamıyor."))
        let auth = makeAuth(fake: fake)
        let vm = TripAssistantViewModel()

        await vm.send("soru", tripID: 2, auth: auth)

        XCTAssertTrue(vm.messages.isEmpty, "Başarısız kullanıcı mesajı sohbette KALMAMALI")
        XCTAssertEqual(vm.sendError, "AI asistanı şu anda kullanılamıyor.")
    }

    func test_send_unauthorized_logsOutAndDoesNotSetSendError() async {
        let fake = FakeAPIClient()
        fake.result = .failure(APIError.unauthorized(message: nil))
        let auth = makeAuth(fake: fake)
        let vm = TripAssistantViewModel()

        await vm.send("soru", tripID: 2, auth: auth)

        XCTAssertFalse(auth.isAuthenticated)
        XCTAssertNil(vm.sendError)
    }

    // MARK: - Retry

    func test_retryLastFailedMessage_resendsTheSameText() async {
        let fake = FakeAPIClient()
        fake.result = .failure(APIError.network(URLError(.notConnectedToInternet)))
        let auth = makeAuth(fake: fake)
        let vm = TripAssistantViewModel()

        await vm.send("başarısız soru", tripID: 2, auth: auth)
        XCTAssertNotNil(vm.sendError)

        fake.result = .success(AssistantResponse(answer: "Bu sefer çalıştı.", references: []))
        await vm.retryLastFailedMessage(tripID: 2, auth: auth)

        XCTAssertEqual(vm.messages.last?.content, "Bu sefer çalıştı.")
        guard case .assistant(_, let message, _) = fake.lastEndpoint else {
            XCTFail("Beklenmeyen endpoint: \(String(describing: fake.lastEndpoint))")
            return
        }
        XCTAssertEqual(message, "başarısız soru")
    }

    func test_retryWithNoFailedMessage_doesNothing() async {
        let fake = FakeAPIClient()
        let auth = makeAuth(fake: fake)
        let vm = TripAssistantViewModel()

        await vm.retryLastFailedMessage(tripID: 2, auth: auth)

        XCTAssertEqual(fake.callCount, 0)
    }

    // MARK: - Bounded history

    func test_send_boundsHistoryToMaxTurns() async {
        let fake = FakeAPIClient()
        fake.result = .success(AssistantResponse(answer: "ok", references: []))
        let auth = makeAuth(fake: fake)
        let vm = TripAssistantViewModel()

        for i in 0..<8 {
            await vm.send("soru \(i)", tripID: 2, auth: auth)
        }

        guard case .assistant(_, _, let history) = fake.lastEndpoint else {
            XCTFail("Beklenmeyen endpoint: \(String(describing: fake.lastEndpoint))")
            return
        }
        XCTAssertLessThanOrEqual(history.count, 6)
    }

    // MARK: - Multi-turn (M27)

    /// "Peki yarın?" gibi bir takip sorusu, önceki turu `history` olarak
    /// TAŞIMALI — sunucu bağlamı (Req 2 "the assistant must understand that
    /// follow-up questions refer to the current trip and conversation").
    func test_followUpQuestion_sendsPriorTurnAsHistory() async {
        let fake = FakeAPIClient()
        fake.result = .success(AssistantResponse(answer: "Bugün 4 durağın var.", references: []))
        let auth = makeAuth(fake: fake)
        let vm = TripAssistantViewModel()

        await vm.send("Bugün hangi yerleri gezeceğim?", tripID: 2, auth: auth)

        fake.result = .success(AssistantResponse(answer: "Yarın için henüz bir planın yok.", references: []))
        await vm.send("Peki yarın?", tripID: 2, auth: auth)

        guard case .assistant(_, let message, let history) = fake.lastEndpoint else {
            XCTFail("Beklenmeyen endpoint: \(String(describing: fake.lastEndpoint))")
            return
        }
        XCTAssertEqual(message, "Peki yarın?")
        XCTAssertEqual(history.count, 2)  // önceki kullanıcı sorusu + asistan cevabı
        XCTAssertEqual(history[0].role, "user")
        XCTAssertEqual(history[0].content, "Bugün hangi yerleri gezeceğim?")
        XCTAssertEqual(history[1].role, "assistant")
        XCTAssertEqual(history[1].content, "Bugün 4 durağın var.")
    }

    func test_multiTurnConversation_preservesFullOrderingInMessages() async {
        let fake = FakeAPIClient()
        fake.result = .success(AssistantResponse(answer: "Bugün 4 durağın var.", references: []))
        let auth = makeAuth(fake: fake)
        let vm = TripAssistantViewModel()

        await vm.send("Bugün hangi yerleri gezeceğim?", tripID: 2, auth: auth)
        fake.result = .success(AssistantResponse(answer: "Zeugma Mozaik Müzesi.", references: []))
        await vm.send("Peki bunlardan hangisi müze?", tripID: 2, auth: auth)

        XCTAssertEqual(vm.messages.map(\.content), [
            "Bugün hangi yerleri gezeceğim?", "Bugün 4 durağın var.",
            "Peki bunlardan hangisi müze?", "Zeugma Mozaik Müzesi.",
        ])
    }

    // MARK: - View disappearance while a request is running

    /// View kapanıp `vm`'e başka hiçbir GÜÇLÜ referans kalmasa bile
    /// (SwiftUI'de View'ın kendi `@State`'i gibi), gönderme sırasında
    /// başlatılan Task onu tamamlanana kadar canlı tutar ve tamamlanma
    /// çökmeden/state'i bozmadan gerçekleşir.
    func test_send_completesSafely_evenWithNoOtherStrongReferenceToViewModel() async {
        let fake = FakeAPIClient()
        fake.result = .success(AssistantResponse(answer: "Cevap", references: []))
        let started = AsyncGate()
        let proceed = AsyncGate()
        fake.startedGate = started
        fake.gate = proceed
        let auth = makeAuth(fake: fake)

        weak var weakVM: TripAssistantViewModel?
        let task: Task<Void, Never>
        do {
            let vm = TripAssistantViewModel()
            weakVM = vm
            task = Task { await vm.send("soru", tripID: 2, auth: auth) }
        }
        // Yerel güçlü referans burada kapsam dışına çıktı — View'ın
        // kaybolması gibi. İstek SÜRERKEN Task'ın kendi yakaladığı referans
        // onu hâlâ canlı tutmalı (aksi halde askıda bir `await` sırasında
        // çökme riski olurdu).
        await started.wait()
        XCTAssertNotNil(weakVM, "İstek sürerken ViewModel hâlâ canlı olmalı")

        await proceed.open()
        await task.value
        // Tamamlandıktan sonra artık başka güçlü referans yok — ARC'ın
        // düzgün TEMİZLEDİĞİNİ doğrular (bellek sızıntısı/retain cycle
        // YOK). Bu bir hata değil, beklenen doğru davranış.
        XCTAssertNil(weakVM, "Tamamlandıktan sonra ViewModel sızıntısız serbest bırakılmalı")
    }
}
