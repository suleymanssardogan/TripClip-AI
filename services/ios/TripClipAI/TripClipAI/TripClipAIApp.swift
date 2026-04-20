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
                    if url.scheme == "tripclip", let id = Int(url.lastPathComponent) {
                        sharedVideoId = id
                        navigateToVideo = true
                    }
                }
            } else {
                LoginView().environmentObject(auth)
            }
        }
    }
}
