import AuthenticationServices
import Foundation
import UIKit

/// Google Sign-In (OAuth 2.0 Authorization Code flow) — `ASWebAuthenticationSession`
/// (sistem çerçevesi) üzerinden. `GoogleSignIn` SPM paketi KASITLI OLARAK
/// eklenmedi: bu projede hiç SPM bağımlılığı yok, Xcode GUI'siz bir ortamda
/// `project.pbxproj`'a paket grafiği eklemek doğrulanamaz bir risk — sistem
/// çerçevesi aynı gerçek Authorization Code akışını (Google'ın kendi
/// `/o/oauth2/v2/auth` uç noktasına karşı) SIFIR ek bağımlılıkla sağlıyor.
/// `client_secret` bu istemciye HİÇBİR ZAMAN gelmez — yalnızca core-api'nin
/// kendisi (confidential client) kod→token değişimini yapar (bkz.
/// AuthEnvironment.googleSignIn, AuthService._exchange_and_verify_google_code).
@MainActor
final class GoogleSignInCoordinator: NSObject {

    enum CoordinatorError: LocalizedError {
        case notConfigured
        case cancelled
        case invalidCallback

        var errorDescription: String? {
            switch self {
            case .notConfigured:   return "Google ile giriş şu anda kullanılamıyor."
            case .cancelled:       return "Google girişi iptal edildi."
            case .invalidCallback: return "Google girişi tamamlanamadı. Lütfen tekrar deneyin."
            }
        }
    }

    private var session: ASWebAuthenticationSession?

    /// Google'ın rıza ekranını açar, kullanıcı onayladıktan sonra dönen
    /// tek kullanımlık `code`'u döner. `state` CSRF koruması için üretilip
    /// doğrulanır — web'in `googleAuth.ts`'teki AYNI deseni (bkz. o dosyanın
    /// doc yorumu).
    func requestAuthorizationCode() async throws -> String {
        guard let clientID = Config.googleClientID else {
            throw CoordinatorError.notConfigured
        }

        let state = UUID().uuidString
        let redirectURI = Config.googleRedirectURI
        guard let scheme = URL(string: redirectURI)?.scheme else {
            throw CoordinatorError.notConfigured
        }

        var components = URLComponents(string: "https://accounts.google.com/o/oauth2/v2/auth")!
        components.queryItems = [
            URLQueryItem(name: "client_id",     value: clientID),
            URLQueryItem(name: "redirect_uri",  value: redirectURI),
            URLQueryItem(name: "response_type", value: "code"),
            URLQueryItem(name: "scope",         value: "openid email profile"),
            URLQueryItem(name: "state",         value: state),
            URLQueryItem(name: "prompt",        value: "select_account"),
        ]

        let callbackURL: URL = try await withCheckedThrowingContinuation { continuation in
            let session = ASWebAuthenticationSession(
                url: components.url!,
                callbackURLScheme: scheme
            ) { url, error in
                if let url {
                    continuation.resume(returning: url)
                } else if let error = error as? ASWebAuthenticationSessionError, error.code == .canceledLogin {
                    continuation.resume(throwing: CoordinatorError.cancelled)
                } else {
                    continuation.resume(throwing: CoordinatorError.invalidCallback)
                }
            }
            session.presentationContextProvider = self
            session.prefersEphemeralWebBrowserSession = true
            self.session = session
            session.start()
        }

        guard
            let returnedState = URLComponents(url: callbackURL, resolvingAgainstBaseURL: false)?
                .queryItems?.first(where: { $0.name == "state" })?.value,
            returnedState == state,
            let code = URLComponents(url: callbackURL, resolvingAgainstBaseURL: false)?
                .queryItems?.first(where: { $0.name == "code" })?.value
        else {
            throw CoordinatorError.invalidCallback
        }

        return code
    }
}

extension GoogleSignInCoordinator: ASWebAuthenticationPresentationContextProviding {
    func presentationAnchor(for session: ASWebAuthenticationSession) -> ASPresentationAnchor {
        UIApplication.shared.connectedScenes
            .compactMap { $0 as? UIWindowScene }
            .flatMap { $0.windows }
            .first { $0.isKeyWindow } ?? ASPresentationAnchor()
    }
}
