import Foundation
import OSLog

@Observable
@MainActor
final class LoginViewModel {

    var email    = ""
    var password = ""
    var error: APIError?
    var isLoading = false

    var canSubmit: Bool {
        !email.trimmingCharacters(in: .whitespaces).isEmpty &&
        password.count >= 3 &&
        !isLoading
    }

    func login(auth: AuthEnvironment) async {
        guard canSubmit else { return }
        isLoading = true
        error = nil
        defer { isLoading = false }

        do {
            try await auth.login(
                email:    email.trimmingCharacters(in: .whitespaces).lowercased(),
                password: password
            )
        } catch let apiError as APIError {
            error = apiError
            Logger.auth.warning("Login failed: \(apiError.localizedDescription ?? "")")
        } catch {
            self.error = .unknown(statusCode: 0)
        }
    }
}
