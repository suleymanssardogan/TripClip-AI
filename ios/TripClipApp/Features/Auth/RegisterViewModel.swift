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
        password.count >= 6 &&
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
