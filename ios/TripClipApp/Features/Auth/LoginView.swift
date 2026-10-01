import SwiftUI

struct LoginView: View {

    @Environment(AuthEnvironment.self) private var auth
    @State private var vm = LoginViewModel()
    @FocusState private var focused: Field?

    private enum Field { case email, password }

    var body: some View {
        ZStack {
            AppColors.background.ignoresSafeArea()

            ScrollView {
                VStack(alignment: .leading, spacing: 28) {
                    // ── Header ──────────────────────────────────────────────
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Tekrar hoş geldin.")
                            .font(.system(.largeTitle, design: .rounded, weight: .bold))
                            .foregroundStyle(AppColors.text)
                        Text("Gezilerine kaldığın yerden devam et.")
                            .font(.body)
                            .foregroundStyle(AppColors.textSecondary)
                    }
                    .padding(.top, 26)

                    // ── Fields ──────────────────────────────────────────────
                    VStack(spacing: 14) {
                        AuthTextField(
                            title: "E-posta",
                            text: $vm.email,
                            keyboardType: .emailAddress,
                            contentType: .emailAddress
                        )
                        .focused($focused, equals: .email)
                        .submitLabel(.next)
                        .onSubmit { focused = .password }

                        AuthTextField(
                            title: "Şifre",
                            text: $vm.password,
                            isSecure: true,
                            contentType: .password
                        )
                        .focused($focused, equals: .password)
                        .submitLabel(.go)
                        .onSubmit { Task { await vm.login(auth: auth) } }
                    }

                    // ── Error ────────────────────────────────────────────────
                    if let error = vm.error {
                        Text(error.localizedDescription ?? "Bir hata oluştu.")
                            .font(.system(size: 14))
                            .foregroundStyle(AppColors.destructive)
                            .multilineTextAlignment(.center)
                            .padding(.horizontal)
                    }

                    // ── Şifremi Unuttum ─────────────────────────────────────
                    NavigationLink("Şifremi unuttum") {
                        ForgotPasswordView()
                    }
                    .font(.system(size: 13, weight: .semibold))
                    .foregroundStyle(AppColors.accentText)
                    .frame(maxWidth: .infinity, alignment: .trailing)

                    // ── Submit ───────────────────────────────────────────────
                    Button {
                        Task { await vm.login(auth: auth) }
                    } label: {
                        Group {
                            if vm.isLoading { ProgressView() }
                            else { Text("Giriş yap").font(.headline) }
                        }
                        .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(.borderedProminent)
                    .controlSize(.large)
                    .tint(AppColors.accent)
                    .disabled(!vm.canSubmit)
                    // Yüklenirken `Text` içeriği bir `ProgressView`e dönüşüyordu
                    // ve VoiceOver'a hiçbir okunabilir etiket kalmıyordu (M36
                    // audit bulgusu — Register/ForgotPassword/Reset/Optimizer
                    // Uygula düğmelerinde AYNI desen düzeltildi).
                    .accessibilityLabel(vm.isLoading ? "Giriş yapılıyor" : "Giriş Yap")
                }
                .padding(.horizontal, 24)
                .padding(.bottom, 48)
            }
        }
        .navigationTitle("Giriş Yap")
        .navigationBarTitleDisplayMode(.inline)
    }
}

// MARK: - Shared Auth TextField

struct AuthTextField: View {
    let title:       String
    @Binding var text: String
    var isSecure:    Bool = false
    var keyboardType: UIKeyboardType = .default
    var contentType: UITextContentType?

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(title)
                .font(.subheadline.weight(.medium))
                .foregroundStyle(AppColors.textSecondary)

            Group {
                if isSecure {
                    SecureField("", text: $text)
                } else {
                    TextField("", text: $text)
                        .keyboardType(keyboardType)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                }
            }
            .textContentType(contentType)
            .font(.system(size: 16))
            .foregroundStyle(AppColors.text)
            .padding(.horizontal, 14)
            .padding(.vertical, 14)
            .background(AppColors.surface2, in: RoundedRectangle(cornerRadius: 12, style: .continuous))
        }
    }
}

#Preview {
    NavigationStack {
        LoginView()
            .environment(AuthEnvironment())
    }
}
