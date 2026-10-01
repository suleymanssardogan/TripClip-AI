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
                VStack(alignment: .leading, spacing: 28) {
                    // ── Header ──────────────────────────────────────────────
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Yola çıkalım.")
                            .font(.system(.largeTitle, design: .rounded, weight: .bold))
                            .foregroundStyle(AppColors.text)
                        Text("Keşfettiğin yerleri kaydetmek için bir hesap oluştur.")
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
                            if vm.isLoading { ProgressView() }
                            else { Text("Hesap oluştur").font(.headline) }
                        }
                        .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(.borderedProminent)
                    .controlSize(.large)
                    .tint(AppColors.accent)
                    .disabled(!vm.canSubmit)
                    .accessibilityLabel(vm.isLoading ? "Kayıt olunuyor" : "Kayıt Ol")

                    VStack(spacing: 3) {
                        Text("Kişisel verilerin işlenmesi hakkında")
                            .foregroundStyle(AppColors.textSecondary)
                        Link("Gizlilik ve Kişisel Veriler", destination: URL(string: "https://tripclip.app/privacy")!)
                            .foregroundStyle(AppColors.accentText)
                    }
                    .font(.system(size: 12))
                    .frame(maxWidth: .infinity)
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
