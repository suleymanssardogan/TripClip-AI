import SwiftUI
import AuthenticationServices

struct LoginView: View {
    @EnvironmentObject var auth: AuthService
    @State private var email = ""
    @State private var password = ""
    @State private var isRegisterMode = false
    @State private var errorMessage: String?
    @State private var successMessage: String?
    @State private var isLoading = false

    var body: some View {
        ZStack {
            LinearGradient(
                colors: [Color(hex: "0A0E27"), Color(hex: "1a1a4e"), Color(hex: "0d2137")],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )
            .ignoresSafeArea()

            VStack(spacing: 0) {
                Spacer()

                // Logo
                VStack(spacing: 12) {
                    ZStack {
                        Circle().fill(Color.blue.opacity(0.15)).frame(width: 100, height: 100)
                        Circle().fill(Color.blue.opacity(0.08)).frame(width: 130, height: 130)
                        Image(systemName: "mappin.and.ellipse")
                            .font(.system(size: 44, weight: .light))
                            .foregroundStyle(
                                LinearGradient(colors: [.white, .blue], startPoint: .top, endPoint: .bottom)
                            )
                    }
                    Text("TripClip AI")
                        .font(.system(size: 32, weight: .bold, design: .rounded))
                        .foregroundColor(.white)
                    Text("Instagram gezilerini\notomatik seyahat planına çevir")
                        .font(.subheadline)
                        .foregroundColor(.white.opacity(0.6))
                        .multilineTextAlignment(.center)
                }

                Spacer()

                VStack(spacing: 12) {
                    if isLoading {
                        ProgressView().tint(.white).scaleEffect(1.3)
                            .frame(height: 52)
                    } else {
                        // Email / Şifre
                        VStack(spacing: 10) {
                            TextField("E-posta", text: $email)
                                .keyboardType(.emailAddress)
                                .autocapitalization(.none)
                                .padding(14)
                                .background(Color.white.opacity(0.1))
                                .cornerRadius(12)
                                .foregroundColor(.white)
                                .tint(.white)

                            SecureField("Şifre", text: $password)
                                .padding(14)
                                .background(Color.white.opacity(0.1))
                                .cornerRadius(12)
                                .foregroundColor(.white)
                                .tint(.white)

                            Button {
                                Task { await handleEmailAuth() }
                            } label: {
                                Text(isRegisterMode ? "Kayıt Ol" : "Giriş Yap")
                                    .fontWeight(.semibold)
                                    .foregroundColor(.white)
                                    .frame(maxWidth: .infinity)
                                    .padding(.vertical, 14)
                                    .background(
                                        LinearGradient(colors: [.blue, Color(hex: "4f46e5")],
                                                       startPoint: .leading, endPoint: .trailing)
                                    )
                                    .cornerRadius(12)
                            }

                            Button {
                                isRegisterMode.toggle()
                                errorMessage = nil
                                successMessage = nil
                            } label: {
                                Text(isRegisterMode ? "Zaten hesabın var mı? Giriş yap" : "Hesap yok mu? Kayıt ol")
                                    .font(.caption)
                                    .foregroundColor(.white.opacity(0.6))
                            }
                        }

                        // Ayırıcı
                        HStack {
                            Rectangle().fill(Color.white.opacity(0.15)).frame(height: 1)
                            Text("veya").font(.caption).foregroundColor(.white.opacity(0.4))
                            Rectangle().fill(Color.white.opacity(0.15)).frame(height: 1)
                        }

                        // Apple Sign In
                        SignInWithAppleButton(.signIn) { request in
                            request.requestedScopes = [.fullName, .email]
                        } onCompletion: { result in
                            Task {
                                isLoading = true
                                errorMessage = nil
                                do {
                                    try await auth.handleAppleSignIn(result: result)
                                } catch {
                                    errorMessage = error.localizedDescription
                                }
                                isLoading = false
                            }
                        }
                        .signInWithAppleButtonStyle(.white)
                        .frame(maxWidth: .infinity)
                        .frame(height: 50)
                        .cornerRadius(14)
                    }

                    if let success = successMessage {
                        HStack(spacing: 8) {
                            Image(systemName: "checkmark.circle.fill")
                                .foregroundColor(.green)
                            Text(success)
                                .font(.caption)
                                .foregroundColor(.green.opacity(0.9))
                        }
                        .multilineTextAlignment(.center)
                    }

                    if let error = errorMessage {
                        Text(error)
                            .font(.caption)
                            .foregroundColor(.red.opacity(0.9))
                            .multilineTextAlignment(.center)
                    }

                    Text("Giriş yaparak Gizlilik Politikası'nı kabul etmiş olursunuz.")
                        .font(.caption2)
                        .foregroundColor(.white.opacity(0.3))
                        .multilineTextAlignment(.center)
                }
                .padding(.horizontal, 28)

                Spacer().frame(height: 50)
            }
        }
    }

    func handleEmailAuth() async {
        guard !email.isEmpty, !password.isEmpty else {
            errorMessage = "E-posta ve şifre boş olamaz"
            return
        }
        isLoading = true
        errorMessage = nil
        successMessage = nil
        do {
            if isRegisterMode {
                try await auth.register(email: email, password: password, username: nil)
                // Kayıt başarılı → giriş ekranına yönlendir
                withAnimation(.easeInOut(duration: 0.3)) {
                    successMessage = "Hesap oluşturuldu! Şimdi giriş yapabilirsin."
                    isRegisterMode = false
                    password = ""    // şifreyi temizle, email saklı kalsın
                }
            } else {
                try await auth.login(email: email, password: password)
            }
        } catch {
            errorMessage = error.localizedDescription
        }
        isLoading = false
    }
}

#Preview {
    LoginView().environmentObject(AuthService.shared)
}
