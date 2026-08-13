import XCTest
@testable import TripClipApp

/// `APIClient.send`'in gerçek 401→refresh→tekrar-dene sarmalayıcısını,
/// `MockURLProtocol` üzerinden gerçek HTTP durum kodlarıyla test eder —
/// `FakeAPIClient` bu sarmalayıcıyı hiç çalıştırmadığı için (bkz.
/// FakeAPIClient.swift doc yorumu), bu davranış M35'e kadar HİÇ test
/// edilmemişti.
@MainActor
final class APIClientTests: XCTestCase {

    override func tearDown() {
        MockURLProtocol.requestHandler = nil
        super.tearDown()
    }

    private func makeClient() -> APIClient {
        APIClient(baseURL: URL(string: "https://test.invalid")!, session: MockURLProtocol.makeSession())
    }

    // MARK: - 401 → refresh → retry

    func test_send_401_retriesWithRefreshedToken_succeeds() async throws {
        // Yalnızca "Bearer new-token" ile gelen istek 200 alır — bu yüzden
        // başarılı bir decode, refreshHandler'ın GERÇEKTEN çağrıldığının ve
        // yeni token'ın tekrar denemede kullanıldığının kanıtıdır.
        MockURLProtocol.requestHandler = { request in
            let authHeader = request.value(forHTTPHeaderField: "Authorization")
            if authHeader == "Bearer new-token" {
                let resp = HTTPURLResponse(url: request.url!, statusCode: 200, httpVersion: nil, headerFields: nil)!
                return (resp, try! JSONSerialization.data(withJSONObject: ["status": "ok"]))
            }
            let resp = HTTPURLResponse(url: request.url!, statusCode: 401, httpVersion: nil, headerFields: nil)!
            return (resp, try! JSONSerialization.data(withJSONObject: ["code": "UNAUTHORIZED", "message": "expired"]))
        }

        let client = makeClient()
        client.refreshHandler = { "new-token" }

        let result: StatusResponse = try await client.send(.registerDeviceToken(token: "x"), token: "old-token")
        XCTAssertEqual(result.status, "ok")
    }

    func test_send_401_refreshHandlerReturnsNil_throwsUnauthorized_doesNotLoop() async {
        MockURLProtocol.requestHandler = { request in
            let resp = HTTPURLResponse(url: request.url!, statusCode: 401, httpVersion: nil, headerFields: nil)!
            return (resp, try! JSONSerialization.data(withJSONObject: ["code": "UNAUTHORIZED", "message": "expired"]))
        }

        let client = makeClient()
        client.refreshHandler = { nil }  // refresh de başarısız oldu

        do {
            let _: StatusResponse = try await client.send(.registerDeviceToken(token: "x"), token: "old-token")
            XCTFail("401 bekleniyordu")
        } catch let error as APIError {
            XCTAssertTrue(error.isUnauthorized)
        } catch {
            XCTFail("Beklenmeyen hata: \(error)")
        }
    }

    func test_send_401_onRefreshEndpointItself_doesNotAttemptNestedRefresh() async {
        MockURLProtocol.requestHandler = { request in
            let resp = HTTPURLResponse(url: request.url!, statusCode: 401, httpVersion: nil, headerFields: nil)!
            return (resp, try! JSONSerialization.data(withJSONObject: ["code": "REFRESH_TOKEN_INVALID", "message": "invalid"]))
        }

        let client = makeClient()
        client.refreshHandler = {
            XCTFail("refresh endpoint'inin kendi 401'i tekrar refresh TETİKLEMEMELİ (sonsuz döngü riski)")
            return nil
        }

        do {
            let _: AuthResponse = try await client.send(.refresh(refreshToken: "x"), token: nil)
            XCTFail("401 bekleniyordu")
        } catch let error as APIError {
            XCTAssertTrue(error.isUnauthorized)
        } catch {
            XCTFail("Beklenmeyen hata: \(error)")
        }
    }

    // MARK: - Pre-auth endpoints must never trigger a refresh (M35 fix)

    /// Şifre sıfırlama, Google girişi vb. `token: nil` ile çağrılan uç
    /// noktalar kendi alan-özgü nedenleriyle 401 dönebilir (ör.
    /// PASSWORD_RESET_TOKEN_EXPIRED) — bunlar oturum süresi dolumuyla
    /// İLGİLİ DEĞİLDİR ve refresh denemesini TETİKLEMEMELİDİR (M35 audit
    /// bulgusu — düzeltme öncesi APIClient.send bunu ayırt etmiyordu).
    func test_send_401_onResetPassword_neverInvokesRefreshHandler() async {
        MockURLProtocol.requestHandler = { request in
            if request.url?.path == "/api/mobile/auth/refresh" {
                XCTFail("Şifre sıfırlama 401'i refresh isteği TETİKLEMEMELİ")
            }
            let resp = HTTPURLResponse(url: request.url!, statusCode: 401, httpVersion: nil, headerFields: nil)!
            return (resp, try! JSONSerialization.data(withJSONObject: ["code": "PASSWORD_RESET_TOKEN_EXPIRED", "message": "süresi doldu"]))
        }

        let client = makeClient()
        client.refreshHandler = { "unused" }

        do {
            let _: StatusResponse = try await client.send(.resetPassword(token: "t", newPassword: "p"), token: nil)
            XCTFail("401 bekleniyordu")
        } catch let error as APIError {
            XCTAssertTrue(error.isUnauthorized)
        } catch {
            XCTFail("Beklenmeyen hata: \(error)")
        }
    }

    func test_send_401_onGoogleSignIn_neverInvokesRefreshHandler() async {
        MockURLProtocol.requestHandler = { request in
            if request.url?.path == "/api/mobile/auth/refresh" {
                XCTFail("Google girişi 401'i refresh isteği TETİKLEMEMELİ")
            }
            let resp = HTTPURLResponse(url: request.url!, statusCode: 401, httpVersion: nil, headerFields: nil)!
            return (resp, try! JSONSerialization.data(withJSONObject: ["code": "GOOGLE_EMAIL_NOT_VERIFIED", "message": "doğrulanmamış"]))
        }

        let client = makeClient()
        client.refreshHandler = { "unused" }

        do {
            let _: AuthResponse = try await client.send(.googleSignIn(code: "c", redirectUri: "https://example.com"), token: nil)
            XCTFail("401 bekleniyordu")
        } catch let error as APIError {
            XCTAssertTrue(error.isUnauthorized)
        } catch {
            XCTFail("Beklenmeyen hata: \(error)")
        }
    }

    // MARK: - Error envelope decoding (both shapes)

    func test_send_decodesFlatMobileBFFErrorEnvelope() async {
        MockURLProtocol.requestHandler = { request in
            let resp = HTTPURLResponse(url: request.url!, statusCode: 400, httpVersion: nil, headerFields: nil)!
            return (resp, try! JSONSerialization.data(withJSONObject: ["code": "DUPLICATE_EMAIL", "message": "Bu e-posta adresi zaten kayıtlı."]))
        }
        let client = makeClient()
        do {
            let _: AuthResponse = try await client.send(.register(email: "x@test.com", password: "p", username: nil), token: nil)
            XCTFail("400 bekleniyordu")
        } catch let error as APIError {
            guard case .server(let code, let message) = error else {
                XCTFail("Beklenmeyen hata tipi: \(error)"); return
            }
            XCTAssertEqual(code, "DUPLICATE_EMAIL")
            XCTAssertEqual(message, "Bu e-posta adresi zaten kayıtlı.")
        } catch {
            XCTFail("Beklenmeyen hata: \(error)")
        }
    }

    func test_send_decodesNestedCoreApiErrorEnvelope() async {
        MockURLProtocol.requestHandler = { request in
            let resp = HTTPURLResponse(url: request.url!, statusCode: 400, httpVersion: nil, headerFields: nil)!
            return (resp, try! JSONSerialization.data(withJSONObject: ["error": ["code": "VALIDATION_ERROR", "message": "Geçersiz istek."]]))
        }
        let client = makeClient()
        do {
            let _: AuthResponse = try await client.send(.register(email: "x@test.com", password: "p", username: nil), token: nil)
            XCTFail("400 bekleniyordu")
        } catch let error as APIError {
            guard case .server(let code, let message) = error else {
                XCTFail("Beklenmeyen hata tipi: \(error)"); return
            }
            XCTAssertEqual(code, "VALIDATION_ERROR")
            XCTAssertEqual(message, "Geçersiz istek.")
        } catch {
            XCTFail("Beklenmeyen hata: \(error)")
        }
    }
}
