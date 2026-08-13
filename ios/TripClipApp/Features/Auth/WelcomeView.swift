import SwiftUI
import AuthenticationServices

struct WelcomeView: View {

    @Environment(AuthEnvironment.self) private var auth
    @Environment(\.colorScheme) private var colorScheme
    @State private var path      = NavigationPath()
    @State private var appleErr  = ""
    @State private var googleErr = ""
    @State private var loading   = false
    @State private var googleCoordinator = GoogleSignInCoordinator()

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
                            .foregroundStyle(AppColors.accentText)
                            .symbolEffect(.pulse)

                        Text("TripClip")
                            .font(.system(size: 42, weight: .black, design: .rounded))
                            .foregroundStyle(AppColors.text)

                        Text("Instagram videolarından\ngezi planı oluştur")
                            .font(.system(size: 16))
                            .foregroundStyle(AppColors.textSecondary)
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
                                .background(AppColors.accent)
                                .foregroundStyle(AppColors.onAccent)
                                .clipShape(RoundedRectangle(cornerRadius: 16))
                        }
                        .buttonStyle(PressableButtonStyle())

                        NavigationLink(value: "register") {
                            Text("Hesap Oluştur")
                                .font(.system(size: 16, weight: .semibold))
                                .frame(maxWidth: .infinity)
                                .padding(.vertical, 16)
                                .background(AppColors.surface2)
                                .foregroundStyle(AppColors.text)
                                .clipShape(RoundedRectangle(cornerRadius: 16))
                        }
                        .buttonStyle(PressableButtonStyle())

                        // ── Divider ─────────────────────────────────────────
                        HStack(spacing: 12) {
                            Rectangle().fill(AppColors.border).frame(height: 1)
                            Text("veya").font(.caption).foregroundStyle(AppColors.textTertiary)
                            Rectangle().fill(AppColors.border).frame(height: 1)
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
                        .signInWithAppleButtonStyle(colorScheme == .dark ? .white : .black)
                        .frame(maxWidth: .infinity)
                        .frame(height: 50)
                        .clipShape(RoundedRectangle(cornerRadius: 16))
                        .disabled(loading)

                        if !appleErr.isEmpty {
                            Text(appleErr)
                                .font(.caption)
                                .foregroundStyle(AppColors.destructive)
                                .multilineTextAlignment(.center)
                        }

                        // ── Google Sign In ───────────────────────────────────
                        // `Config.googleClientID` boşsa (varsayılan, GOOGLE_CLIENT_ID
                        // set edilmemiş) buton hiç GÖRÜNMEZ — web'in aynı
                        // `isGoogleSignInConfigured()` deseniyle tutarlı.
                        if Config.googleClientID != nil {
                            Button {
                                Task {
                                    loading   = true
                                    googleErr = ""
                                    do {
                                        let code = try await googleCoordinator.requestAuthorizationCode()
                                        try await auth.googleSignIn(code: code, redirectUri: Config.googleRedirectURI)
                                    } catch {
                                        googleErr = error.localizedDescription
                                    }
                                    loading = false
                                }
                            } label: {
                                HStack(spacing: 10) {
                                    Image(systemName: "g.circle.fill")
                                        .font(.system(size: 18))
                                    Text("Google ile devam et")
                                        .font(.system(size: 16, weight: .semibold))
                                }
                                .frame(maxWidth: .infinity)
                                .padding(.vertical, 14)
                                .background(AppColors.surface2)
                                .foregroundStyle(AppColors.text)
                                .clipShape(RoundedRectangle(cornerRadius: 16))
                                .overlay(
                                    RoundedRectangle(cornerRadius: 16)
                                        .stroke(AppColors.border, lineWidth: 1)
                                )
                            }
                            .buttonStyle(PressableButtonStyle())
                            .disabled(loading)

                            if !googleErr.isEmpty {
                                Text(googleErr)
                                    .font(.caption)
                                    .foregroundStyle(AppColors.destructive)
                                    .multilineTextAlignment(.center)
                            }
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

#Preview {
    WelcomeView()
        .environment(AuthEnvironment())
}
