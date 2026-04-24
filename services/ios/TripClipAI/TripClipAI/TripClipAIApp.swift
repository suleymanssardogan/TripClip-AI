import SwiftUI

@main
struct TripClipAIApp: App {
    @StateObject private var auth = AuthService.shared
    @State private var sharedVideoId: Int?
    @State private var navigateToVideo = false

    var body: some Scene {
        WindowGroup {
            if auth.isAuthenticated {
                NavigationStack {
                    HomeView()
                        .navigationDestination(isPresented: $navigateToVideo) {
                            if let id = sharedVideoId {
                                ResultsView(videoId: id)
                            }
                        }
                }
                .environmentObject(auth)
                .onOpenURL { url in
                    guard url.scheme == "tripclip" else { return }

                    // tripclip://123  → video sonuçlarına git
                    if let id = Int(url.lastPathComponent) {
                        sharedVideoId   = id
                        navigateToVideo = true
                        return
                    }

                    // tripclip://share?url=https://instagram.com/reel/...
                    // Share extension'dan gelen Instagram URL'i — şimdilik sadece aç
                    // (ileride URL'den video indirme eklenebilir)
                }
            } else {
                LoginView().environmentObject(auth)
            }
        }
    }
}
