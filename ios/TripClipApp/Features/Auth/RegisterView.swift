import SwiftUI

struct RegisterView: View {

    @Environment(AuthEnvironment.self) private var auth
    @State private var vm = RegisterViewModel()
    @FocusState private var focused: Field?

    private enum Field { case email, username, password }

    var body: some View {
        ZStack {
            AppColors.background.ignoresSafeArea()

            ScrollView {
                VStack(spacing: 32) {
                    // ── Header ──────────────────────────────────────────────
                    VStack(spacing: 8) {
                        Image(systemName: "person.badge.plus.fill")
                            .font(.system(size: 52))
                            .foregroundStyle(AppColors.accentText)
                        Text("Hesap Oluştur")
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
                        .onSubmit { focused = .username }

                        AuthTextField(
                            title: "Kullanıcı Adı (opsiyonel)",
                            text: $vm.username,
                            contentType: .username
                        )
                        .focused($focused, equals: .username)
                        .submitLabel(.next)
                        .onSubmit { focused = .password }

                        AuthTextField(
                            title: "Şifre (min. 8 karakter)",
                            text: $vm.password,
                            isSecure: true,
                            contentType: .newPassword
                        )
                        .focused($focused, equals: .password)
                        .submitLabel(.go)
                        .onSubmit { Task { await vm.register(auth: auth) } }
                    }

                    // ── Error ────────────────────────────────────────────────
                    if let error = vm.error {
                        Text(error.localizedDescription ?? "Bir hata oluştu.")
                            .font(.system(size: 14))
                            .foregroundStyle(AppColors.destructive)
                            .multilineTextAlignment(.center)
                            .padding(.horizontal)
                    }

                    // ── Submit ───────────────────────────────────────────────
                    Button {
                        Task { await vm.register(auth: auth) }
                    } label: {
                        Group {
                            if vm.isLoading {
                                ProgressView().tint(AppColors.onAccent)
                            } else {
                                Text("Kayıt Ol")
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
                    .accessibilityLabel(vm.isLoading ? "Kayıt olunuyor" : "Kayıt Ol")
                }
                .padding(.horizontal, 24)
                .padding(.bottom, 48)
            }
        }
        .navigationTitle("Kayıt Ol")
        .navigationBarTitleDisplayMode(.inline)
    }
}

#Preview {
    NavigationStack {
        RegisterView()
            .environment(AuthEnvironment())
    }
}
