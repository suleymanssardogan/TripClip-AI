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
                VStack(spacing: 32) {
                    // ── Header ──────────────────────────────────────────────
                    VStack(spacing: 8) {
                        Image(systemName: "person.circle.fill")
                            .font(.system(size: 52))
                            .foregroundStyle(AppColors.accentText)
                        Text("Giriş Yap")
                            .font(.system(size: 28, weight: .bold))
                            .foregroundStyle(AppColors.text)
                    }
                    .padding(.top, 40)

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
                            if vm.isLoading {
                                ProgressView().tint(AppColors.onAccent)
                            } else {
                                Text("Giriş Yap")
                                    .font(.system(size: 16, weight: .semibold))
                            }
                        }
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 16)
                        .background(vm.canSubmit ? AppColors.accent : AppColors.accent.opacity(0.35))
                        .foregroundStyle(AppColors.onAccent)
                        .clipShape(RoundedRectangle(cornerRadius: 16))
                    }
                    .buttonStyle(PressableButtonStyle())
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
                .font(.system(size: 12, weight: .medium))
                .foregroundStyle(AppColors.textSecondary)
                .textCase(.uppercase)
                .tracking(1)

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
            .background(AppColors.surface2)
            .clipShape(RoundedRectangle(cornerRadius: 12))
            .overlay(
                RoundedRectangle(cornerRadius: 12)
                    .stroke(AppColors.borderStrong, lineWidth: 1)
            )
        }
    }
}

#Preview {
    NavigationStack {
        LoginView()
            .environment(AuthEnvironment())
    }
}
