import Foundation
import OSLog

@Observable
@MainActor
final class RegisterViewModel {

    var email    = ""
    var password = ""
    var username = ""
    var error: APIError?
    var isLoading = false

    var canSubmit: Bool {
        !email.trimmingCharacters(in: .whitespaces).isEmpty &&
        // Sunucunun TEK paylaşılan kuralı (kayıt VE şifre sıfırlama) 8
        // karakter (bkz. core-api _validate_password_strength,
        // ResetPasswordViewModel'in AYNI eşiği). Burası önceden 6'ydı —
        // 6-7 karakterlik bir şifre istemci tarafında GEÇERLİ görünüp
        // sunucuda deterministik olarak 422/VALIDATION_ERROR ile
        // reddediliyordu (M36 audit bulgusu).
        password.count >= 8 &&
        !isLoading
    }

    func register(auth: AuthEnvironment) async {
        guard canSubmit else { return }
        isLoading = true
        error = nil
        defer { isLoading = false }

        let resolvedUsername = username.trimmingCharacters(in: .whitespaces)

        do {
            try await auth.register(
                email:    email.trimmingCharacters(in: .whitespaces).lowercased(),
                password: password,
                username: resolvedUsername.isEmpty ? nil : resolvedUsername
            )
        } catch let apiError as APIError {
            error = apiError
            Logger.auth.warning("Register failed: \(apiError.localizedDescription ?? "")")
        } catch {
            self.error = .unknown(statusCode: 0)
        }
    }
}
