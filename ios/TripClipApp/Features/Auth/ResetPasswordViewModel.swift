import Foundation
import OSLog

@Observable
@MainActor
final class ResetPasswordViewModel {

    var token           = ""
    var newPassword     = ""
    var confirmPassword = ""
    var error: APIError?
    var isLoading  = false
    private(set) var didSucceed = false

    var canSubmit: Bool {
        !token.trimmingCharacters(in: .whitespaces).isEmpty &&
        newPassword.count >= 8 &&
        !isLoading
    }

    func submit(auth: AuthEnvironment) async {
        guard canSubmit else { return }
        error = nil

        guard newPassword == confirmPassword else {
            error = .server(code: "PASSWORD_MISMATCH", message: "Şifreler eşleşmiyor.")
            return
        }

        isLoading = true
        defer { isLoading = false }

        do {
            try await auth.resetPassword(
                token:       token.trimmingCharacters(in: .whitespaces),
                newPassword: newPassword
            )
            didSucceed = true
        } catch let apiError as APIError {
            error = apiError
            Logger.auth.warning("Reset-password failed: \(apiError.localizedDescription ?? "")")
        } catch {
            self.error = .unknown(statusCode: 0)
        }
    }
}
