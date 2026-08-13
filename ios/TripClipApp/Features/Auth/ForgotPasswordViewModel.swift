import Foundation
import OSLog

@Observable
@MainActor
final class ForgotPasswordViewModel {

    var email      = ""
    var isLoading  = false
    /// Sunucu hesap var/yok fark etmeksizin AYNI genel yanıtı döner (kullanıcı
    /// numaralandırmayı önlemek için) — bu yüzden burada `error` YOK, yalnızca
    /// `didSubmit`; ağ hatası dahi olsa AYNI genel mesaj gösterilir (web'in
    /// forgot-password sayfasıyla AYNI karar, bkz. o dosyanın doc yorumu).
    private(set) var didSubmit = false

    var canSubmit: Bool {
        !email.trimmingCharacters(in: .whitespaces).isEmpty && !isLoading
    }

    func submit(auth: AuthEnvironment) async {
        guard canSubmit else { return }
        isLoading = true
        defer { isLoading = false }

        do {
            try await auth.forgotPassword(email: email.trimmingCharacters(in: .whitespaces).lowercased())
        } catch {
            Logger.auth.warning("Forgot-password request failed (still showing generic success): \(String(describing: error))")
        }
        didSubmit = true
    }
}
