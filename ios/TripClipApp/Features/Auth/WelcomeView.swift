import SwiftUI
import AuthenticationServices

struct WelcomeView: View {

    @Environment(AuthEnvironment.self) private var auth
    @Environment(\.colorScheme) private var colorScheme
    @State private var path = NavigationPath()
    @State private var appleErr = ""
    @State private var googleErr = ""
    @State private var loading = false
    @State private var googleCoordinator = GoogleSignInCoordinator()

    var body: some View {
        NavigationStack(path: $path) {
            VStack(spacing: 0) {
                ScrollView {
                    VStack(alignment: .leading, spacing: 0) {
                        HStack(spacing: 0) {
                            Text("tripclip")
                                .foregroundStyle(AppColors.text)
                            Text(".")
                                .foregroundStyle(AppColors.accentText)
                        }
                        .font(.system(.title2, design: .rounded, weight: .heavy))
                        .tracking(-1.2)
                        .padding(.top, 14)

                        Rectangle()
                            .fill(Color.clear)
                            .frame(height: 238)
                            .overlay {
                                Image("WelcomePhoto")
                                    .resizable()
                                    .scaledToFill()
                            }
                            .clipped()
                            .clipShape(RoundedRectangle(cornerRadius: 22, style: .continuous))
                            .accessibilityLabel("İstanbul Boğazı'nı gösteren temsili seyahat görseli")
                            .padding(.top, 24)

                        Text("İstanbul, Türkiye · Temsili görsel")
                            .font(.caption2)
                            .foregroundStyle(AppColors.textTertiary)
                            .padding(.top, 9)

                        Text("Gördüğün yerler,\ngideceğin yerler.")
                            .font(.system(.largeTitle, design: .rounded, weight: .bold))
                            .tracking(-1.4)
                            .foregroundStyle(AppColors.text)
                            .fixedSize(horizontal: false, vertical: true)
                            .padding(.top, 27)

                        Text("Gezi videolarındaki durakları keşfet. Beğendiklerini kaydet, kendi rotanı oluştur.")
                            .font(.body)
                            .foregroundStyle(AppColors.textSecondary)
                            .fixedSize(horizontal: false, vertical: true)
                            .lineSpacing(3)
                            .padding(.top, 12)
                    }
                    .padding(.horizontal, 22)
                    .padding(.bottom, 24)
                    .frame(maxWidth: 560)
                    .frame(maxWidth: .infinity)
                }
                .scrollIndicators(.hidden)

                actions
            }
            .background(AppColors.background.ignoresSafeArea())
            .navigationDestination(for: String.self) { destination in
                switch destination {
                case "login": LoginView()
                case "register": RegisterView()
                default: EmptyView()
                }
            }
        }
        .tint(AppColors.accentText)
    }

    private var actions: some View {
        VStack(spacing: 10) {
            NavigationLink(value: "register") {
                Text("Ücretsiz başla")
                    .font(.headline)
                    .frame(maxWidth: .infinity)
            }
            .buttonStyle(.borderedProminent)
            .controlSize(.large)
            .tint(AppColors.accent)

            NavigationLink(value: "login") {
                Text("Giriş yap")
                    .font(.headline)
                    .frame(maxWidth: .infinity)
            }
            .buttonStyle(.bordered)
            .controlSize(.large)

            SignInWithAppleButton(.signIn) { request in
                request.requestedScopes = [.fullName, .email]
            } onCompletion: { result in
                Task {
                    loading = true
                    appleErr = ""
                    do { try await auth.appleSignIn(result: result) }
                    catch { appleErr = error.localizedDescription }
                    loading = false
                }
            }
            .signInWithAppleButtonStyle(colorScheme == .dark ? .white : .black)
            .frame(height: 51)
            .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
            .disabled(loading)
            .padding(.top, 4)

            if !appleErr.isEmpty {
                Text(appleErr)
                    .font(.caption)
                    .foregroundStyle(AppColors.destructive)
                    .multilineTextAlignment(.center)
            }

            if Config.googleClientID != nil {
                Button {
                    Task {
                        loading = true
                        googleErr = ""
                        do {
                            let code = try await googleCoordinator.requestAuthorizationCode()
                            try await auth.googleSignIn(code: code, redirectUri: Config.googleRedirectURI)
                        } catch { googleErr = error.localizedDescription }
                        loading = false
                    }
                } label: {
                    Text("Google ile devam et")
                        .font(.subheadline.weight(.semibold))
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(.bordered)
                .controlSize(.large)
                .disabled(loading)

                if !googleErr.isEmpty {
                    Text(googleErr)
                        .font(.caption)
                        .foregroundStyle(AppColors.destructive)
                        .multilineTextAlignment(.center)
                }
            }

            HStack(spacing: 4) {
                Text("Bilgi için")
                Link("Gizlilik", destination: URL(string: "https://tripclip.app/privacy")!)
                Text("ve")
                Link("Koşullar'ı", destination: URL(string: "https://tripclip.app/terms")!)
                Text("incele.")
            }
            .font(.caption2)
            .foregroundStyle(AppColors.textSecondary)
            .minimumScaleFactor(0.85)
            .padding(.top, 5)
        }
        .padding(.horizontal, 22)
        .padding(.top, 14)
        .padding(.bottom, 10)
        .frame(maxWidth: 560)
        .frame(maxWidth: .infinity)
        .background(AppColors.background)
        .overlay(alignment: .top) {
            Rectangle().fill(AppColors.border).frame(height: 1)
        }
    }
}

#Preview {
    WelcomeView().environment(AuthEnvironment())
}
