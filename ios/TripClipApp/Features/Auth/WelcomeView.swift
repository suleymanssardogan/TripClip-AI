import SwiftUI
import AuthenticationServices

struct WelcomeView: View {

    @Environment(AuthEnvironment.self) private var auth
    @State private var path     = NavigationPath()
    @State private var appleErr = ""
    @State private var loading  = false

    var body: some View {
        NavigationStack(path: $path) {
            ZStack {
                AppColors.background.ignoresSafeArea()

                VStack(spacing: 0) {
                    Spacer()

                    // ── Logo / Hero ─────────────────────────────────────────
                    VStack(spacing: 16) {
                        Image(systemName: "mappin.and.ellipse")
                            .font(.system(size: 64))
                            .foregroundStyle(AppColors.neon)
                            .symbolEffect(.pulse)

                        Text("TripClip")
                            .font(.system(size: 42, weight: .black, design: .rounded))
                            .foregroundStyle(.white)

                        Text("Instagram videolarından\ngezi planı oluştur")
                            .font(.system(size: 16))
                            .foregroundStyle(.white.opacity(0.55))
                            .multilineTextAlignment(.center)
                    }

                    Spacer()

                    // ── CTA Buttons ─────────────────────────────────────────
                    VStack(spacing: 12) {
                        NavigationLink(value: "login") {
                            Label("Giriş Yap", systemImage: "arrow.right.circle.fill")
                                .font(.system(size: 16, weight: .semibold))
                                .frame(maxWidth: .infinity)
                                .padding(.vertical, 16)
                                .background(AppColors.neon)
                                .foregroundStyle(Color.black)
                                .clipShape(RoundedRectangle(cornerRadius: 16))
                        }

                        NavigationLink(value: "register") {
                            Text("Hesap Oluştur")
                                .font(.system(size: 16, weight: .semibold))
                                .frame(maxWidth: .infinity)
                                .padding(.vertical, 16)
                                .background(Color.white.opacity(0.08))
                                .foregroundStyle(.white)
                                .clipShape(RoundedRectangle(cornerRadius: 16))
                        }

                        // ── Divider ─────────────────────────────────────────
                        HStack(spacing: 12) {
                            Rectangle().fill(Color.white.opacity(0.12)).frame(height: 1)
                            Text("veya").font(.caption).foregroundStyle(.white.opacity(0.4))
                            Rectangle().fill(Color.white.opacity(0.12)).frame(height: 1)
                        }

                        // ── Apple Sign In ────────────────────────────────────
                        SignInWithAppleButton(.signIn) { request in
                            request.requestedScopes = [.fullName, .email]
                        } onCompletion: { result in
                            Task {
                                loading  = true
                                appleErr = ""
                                do {
                                    try await auth.appleSignIn(result: result)
                                } catch {
                                    appleErr = error.localizedDescription
                                }
                                loading = false
                            }
                        }
                        .signInWithAppleButtonStyle(.white)
                        .frame(maxWidth: .infinity)
                        .frame(height: 50)
                        .clipShape(RoundedRectangle(cornerRadius: 16))
                        .disabled(loading)

                        if !appleErr.isEmpty {
                            Text(appleErr)
                                .font(.caption)
                                .foregroundStyle(AppColors.coral)
                                .multilineTextAlignment(.center)
                        }
                    }
                    .padding(.horizontal, 24)
                    .padding(.bottom, 48)
                }
            }
            .navigationDestination(for: String.self) { destination in
                switch destination {
                case "login":    LoginView()
                case "register": RegisterView()
                default:         EmptyView()
                }
            }
        }
    }
}

// MARK: - App Colors

enum AppColors {
    static let background = Color(red: 0.06, green: 0.07, blue: 0.13)
    static let surface    = Color(red: 0.10, green: 0.11, blue: 0.18)
    static let neon       = Color(red: 0.30, green: 1.00, blue: 0.76)
    static let coral      = Color(red: 1.00, green: 0.42, blue: 0.29)
    static let violet     = Color(red: 0.54, green: 0.36, blue: 0.95)
    static let muted      = Color.white.opacity(0.45)
}

#Preview {
    WelcomeView()
        .environment(AuthEnvironment())
}
