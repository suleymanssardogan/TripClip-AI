import SwiftUI

struct ResetPasswordView: View {

    /// Sağlandığında, "Giriş sayfasına dön" bunu KENDİ `dismiss()`i yerine
    /// çağırır — bu ekranı AÇAN atanın (bkz. `ForgotPasswordView`) kendi
    /// `dismiss`ini önceden yakalayıp geçirdiği bir tamamlama closure'ı,
    /// böylece tek dokunuşla zincirdeki ATA seviyesine (Login) kadar
    /// kapanır, yalnızca bu ekrana DEĞİL (M36 audit bulgusu — bu düğme
    /// önceden "Giriş sayfasına dön" diyip yalnızca bir üst ekrana
    /// ["Şifremi Unuttum"] dönüyordu). Sağlanmazsa (ör. önizleme/gelecekte
    /// başka bir yerden açılırsa) kendi `dismiss()`ine düşer.
    var onFinished: (() -> Void)? = nil

    @Environment(AuthEnvironment.self) private var auth
    @Environment(\.dismiss) private var dismiss
    @State private var vm = ResetPasswordViewModel()
    @FocusState private var focused: Field?

    private enum Field { case token, password, confirm }

    var body: some View {
        ZStack {
            AppColors.background.ignoresSafeArea()

            ScrollView {
                VStack(spacing: 32) {
                    VStack(spacing: 8) {
                        Image(systemName: "lock.rotation")
                            .font(.system(size: 52))
                            .foregroundStyle(AppColors.accentText)
                        Text("Yeni Şifre Belirle")
                            .font(.system(size: 28, weight: .bold))
                            .foregroundStyle(AppColors.text)
                    }
                    .padding(.top, 40)

                    if vm.didSucceed {
                        VStack(spacing: 12) {
                            Image(systemName: "checkmark.circle.fill")
                                .font(.system(size: 36))
                                .foregroundStyle(AppColors.success)
                            Text("Şifreniz güncellendi. Yeni şifrenizle giriş yapabilirsiniz.")
                                .font(.system(size: 14))
                                .foregroundStyle(AppColors.textSecondary)
                                .multilineTextAlignment(.center)
                        }
                        .padding(.horizontal)

                        Button {
                            if let onFinished { onFinished() } else { dismiss() }
                        } label: {
                            Text("Giriş sayfasına dön")
                                .font(.system(size: 16, weight: .semibold))
                                .frame(maxWidth: .infinity)
                                .padding(.vertical, 16)
                                .background(AppColors.accent)
                                .foregroundStyle(AppColors.onAccent)
                                .clipShape(RoundedRectangle(cornerRadius: 16))
                        }
                        .buttonStyle(PressableButtonStyle())
                    } else {
                        Text("E-postanıza gelen sıfırlama linkindeki kodu ve yeni şifrenizi girin.")
                            .font(.system(size: 14))
                            .foregroundStyle(AppColors.textSecondary)
                            .multilineTextAlignment(.center)
                            .padding(.horizontal)

                        VStack(spacing: 14) {
                            AuthTextField(title: "Sıfırlama Kodu", text: $vm.token)
                                .focused($focused, equals: .token)
                                .submitLabel(.next)
                                .onSubmit { focused = .password }

                            AuthTextField(
                                title: "Yeni Şifre", text: $vm.newPassword,
                                isSecure: true, contentType: .newPassword
                            )
                            .focused($focused, equals: .password)
                            .submitLabel(.next)
                            .onSubmit { focused = .confirm }

                            AuthTextField(
                                title: "Yeni Şifre (Tekrar)", text: $vm.confirmPassword,
                                isSecure: true, contentType: .newPassword
                            )
                            .focused($focused, equals: .confirm)
                            .submitLabel(.go)
                            .onSubmit { Task { await vm.submit(auth: auth) } }
                        }

                        if let error = vm.error {
                            Text(error.localizedDescription ?? "Bir hata oluştu.")
                                .font(.system(size: 14))
                                .foregroundStyle(AppColors.destructive)
                                .multilineTextAlignment(.center)
                                .padding(.horizontal)
                        }

                        Button {
                            Task { await vm.submit(auth: auth) }
                        } label: {
                            Group {
                                if vm.isLoading {
                                    ProgressView().tint(AppColors.onAccent)
                                } else {
                                    Text("Şifreyi Güncelle")
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
                        .accessibilityLabel(vm.isLoading ? "Güncelleniyor" : "Şifreyi Güncelle")
                    }
                }
                .padding(.horizontal, 24)
                .padding(.bottom, 48)
            }
        }
        .navigationTitle("Yeni Şifre")
        .navigationBarTitleDisplayMode(.inline)
    }
}

#Preview {
    NavigationStack {
        ResetPasswordView()
            .environment(AuthEnvironment())
    }
}
