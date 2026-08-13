import SwiftUI

struct ForgotPasswordView: View {

    @Environment(AuthEnvironment.self) private var auth
    @Environment(\.dismiss) private var dismiss
    @State private var vm = ForgotPasswordViewModel()
    @FocusState private var focused: Bool

    var body: some View {
        ZStack {
            AppColors.background.ignoresSafeArea()

            ScrollView {
                VStack(spacing: 32) {
                    VStack(spacing: 8) {
                        Image(systemName: "key.horizontal.fill")
                            .font(.system(size: 52))
                            .foregroundStyle(AppColors.accentText)
                        Text("Şifremi Unuttum")
                            .font(.system(size: 28, weight: .bold))
                            .foregroundStyle(AppColors.text)
                    }
                    .padding(.top, 40)

                    if vm.didSubmit {
                        VStack(spacing: 12) {
                            Image(systemName: "checkmark.circle.fill")
                                .font(.system(size: 36))
                                .foregroundStyle(AppColors.success)
                            Text("Bu e-posta adresine kayıtlı bir hesap varsa, şifre sıfırlama linki gönderildi. Gelen kutunuzu kontrol edin.")
                                .font(.system(size: 14))
                                .foregroundStyle(AppColors.textSecondary)
                                .multilineTextAlignment(.center)
                        }
                        .padding(.horizontal)

                        // `onFinished`, `ResetPasswordView`in "Giriş sayfasına dön"
                        // düğmesinin GERÇEKTEN Login'e dönmesini sağlar — kendi
                        // `dismiss()`ini çağırsaydı yalnızca BİR seviye (bu ekrana)
                        // dönerdi (M36 audit bulgusu). Standart SwiftUI deseni:
                        // her ata KENDİ `dismiss`ini yakalayıp bir tamamlama
                        // closure'ı olarak aşağı geçirir; en derindeki ekran bunu
                        // çağırdığında ZİNCİRDEKİ o seviye (ve üzerindeki her şey,
                        // ResetPasswordView dahil) tek seferde kapanır.
                        NavigationLink("Sıfırlama kodun var mı? Şifreni sıfırla") {
                            ResetPasswordView(onFinished: { dismiss() })
                        }
                        .font(.system(size: 14, weight: .semibold))
                        .foregroundStyle(AppColors.accentText)
                    } else {
                        Text("Hesabınıza kayıtlı e-posta adresini girin, size bir şifre sıfırlama linki gönderelim.")
                            .font(.system(size: 14))
                            .foregroundStyle(AppColors.textSecondary)
                            .multilineTextAlignment(.center)
                            .padding(.horizontal)

                        AuthTextField(
                            title: "E-posta",
                            text: $vm.email,
                            keyboardType: .emailAddress,
                            contentType: .emailAddress
                        )
                        .focused($focused)
                        .submitLabel(.send)
                        .onSubmit { Task { await vm.submit(auth: auth) } }

                        Button {
                            Task { await vm.submit(auth: auth) }
                        } label: {
                            Group {
                                if vm.isLoading {
                                    ProgressView().tint(AppColors.onAccent)
                                } else {
                                    Text("Sıfırlama Linki Gönder")
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
                        .accessibilityLabel(vm.isLoading ? "Gönderiliyor" : "Sıfırlama Linki Gönder")
                    }
                }
                .padding(.horizontal, 24)
                .padding(.bottom, 48)
            }
        }
        .navigationTitle("Şifremi Unuttum")
        .navigationBarTitleDisplayMode(.inline)
    }
}

#Preview {
    NavigationStack {
        ForgotPasswordView()
            .environment(AuthEnvironment())
    }
}
