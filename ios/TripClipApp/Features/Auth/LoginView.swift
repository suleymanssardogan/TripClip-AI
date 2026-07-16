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
                            .foregroundStyle(AppColors.neon)
                        Text("Giriş Yap")
                            .font(.system(size: 28, weight: .bold))
                            .foregroundStyle(.white)
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
                            .foregroundStyle(AppColors.coral)
                            .multilineTextAlignment(.center)
                            .padding(.horizontal)
                    }

                    // ── Submit ───────────────────────────────────────────────
                    Button {
                        Task { await vm.login(auth: auth) }
                    } label: {
                        Group {
                            if vm.isLoading {
                                ProgressView().tint(.black)
                            } else {
                                Text("Giriş Yap")
                                    .font(.system(size: 16, weight: .semibold))
                            }
                        }
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 16)
                        .background(vm.canSubmit ? AppColors.neon : AppColors.neon.opacity(0.35))
                        .foregroundStyle(.black)
                        .clipShape(RoundedRectangle(cornerRadius: 16))
                    }
                    .buttonStyle(PressableButtonStyle())
                    .disabled(!vm.canSubmit)
                }
                .padding(.horizontal, 24)
                .padding(.bottom, 48)
            }
        }
        .navigationTitle("Giriş Yap")
        .navigationBarTitleDisplayMode(.inline)
        .toolbarColorScheme(.dark, for: .navigationBar)
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
                .foregroundStyle(AppColors.muted)
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
            .foregroundStyle(.white)
            .padding(.horizontal, 14)
            .padding(.vertical, 14)
            .background(AppColors.surface)
            .clipShape(RoundedRectangle(cornerRadius: 12))
            .overlay(
                RoundedRectangle(cornerRadius: 12)
                    .stroke(Color.white.opacity(0.1), lineWidth: 1)
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
