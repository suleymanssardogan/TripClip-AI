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
                            .foregroundStyle(AppColors.neon)
                        Text("Hesap Oluştur")
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
                            title: "Şifre (min. 6 karakter)",
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
                            .foregroundStyle(AppColors.coral)
                            .multilineTextAlignment(.center)
                            .padding(.horizontal)
                    }

                    // ── Submit ───────────────────────────────────────────────
                    Button {
                        Task { await vm.register(auth: auth) }
                    } label: {
                        Group {
                            if vm.isLoading {
                                ProgressView().tint(.black)
                            } else {
                                Text("Kayıt Ol")
                                    .font(.system(size: 16, weight: .semibold))
                            }
                        }
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 16)
                        .background(vm.canSubmit ? AppColors.neon : AppColors.neon.opacity(0.35))
                        .foregroundStyle(.black)
                        .clipShape(RoundedRectangle(cornerRadius: 16))
                    }
                    .disabled(!vm.canSubmit)
                }
                .padding(.horizontal, 24)
                .padding(.bottom, 48)
            }
        }
        .navigationTitle("Kayıt Ol")
        .navigationBarTitleDisplayMode(.inline)
        .toolbarColorScheme(.dark, for: .navigationBar)
    }
}

#Preview {
    NavigationStack {
        RegisterView()
            .environment(AuthEnvironment())
    }
}
