import SwiftUI

struct AIConsentView: View {
    let userID: Int
    var onGranted: () -> Void
    var onDeclined: () -> Void
    @State private var failed = false

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    Text("AI ile veri paylaşımı").font(.title2.bold())
                    Text(AIConsentStore.disclosure).font(.body)
                    Link("Gizlilik politikasını oku", destination: TripClipConfig.privacyURL)
                    if failed { Text("İzin kaydedilemedi. Lütfen tekrar dene.").foregroundStyle(.red) }
                    Button("İzin ver ve devam et") {
                        if AIConsentStore.grant(userID: userID) { onGranted() }
                        else { failed = true }
                    }
                    .buttonStyle(.borderedProminent).controlSize(.large)
                    Button("Şimdi değil", action: onDeclined).buttonStyle(.bordered)
                }
                .padding(24)
                .frame(maxWidth: 560, alignment: .leading)
                .frame(maxWidth: .infinity)
            }
            .navigationTitle("Veri paylaşımı")
            .navigationBarTitleDisplayMode(.inline)
        }
    }
}

struct PrivacySettingsView: View {
    @Environment(AuthEnvironment.self) private var auth
    @State private var consent = false
    @State private var showConsent = false

    var body: some View {
        List {
            Section("Veri paylaşımı") {
                Text("AI sağlayıcısı: \(TripClipConfig.aiProviderName)")
                Text(consent ? "AI paylaşım izni açık" : "AI paylaşım izni kapalı")
                if consent {
                    Button("AI paylaşım iznini geri al", role: .destructive) {
                        AIConsentStore.revoke()
                        consent = false
                    }
                } else {
                    Button("AI paylaşım iznini incele") { showConsent = true }
                }
                Text("İzni geri almak yeni analiz ve mesaj gönderimlerini engeller. Başlamış analizleri durdurmaz veya önceki verileri silmez. Hesabını ana sayfadaki hesap menüsünden silebilirsin.")
                    .font(.footnote).foregroundStyle(.secondary)
            }
            Section("Yasal bilgiler") {
                Link("Gizlilik ve kişisel veriler", destination: TripClipConfig.privacyURL)
                Link("Kullanım koşulları", destination: TripClipConfig.termsURL)
            }
            Section("AI sonuçları") {
                Text("AI sonuçları hatalı olabilir. Yerleri, çalışma saatlerini ve rota koşullarını seyahatten önce doğrula.")
            }
        }
        .navigationTitle("Gizlilik")
        .onAppear { consent = AIConsentStore.hasConsent(userID: auth.user?.id ?? 0) }
        .sheet(isPresented: $showConsent) {
            AIConsentView(userID: auth.user?.id ?? 0, onGranted: {
                consent = true; showConsent = false
            }, onDeclined: { showConsent = false })
        }
    }
}
