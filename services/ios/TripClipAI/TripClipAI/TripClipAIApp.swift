import SwiftUI
@main
struct TripClipAIApp: App {
    @State private var sharedVideoId: Int? = nil
    @State private var navigateToVideo = false
    
    var body: some Scene {
        WindowGroup {
            NavigationStack {
                ContentView()
                    .navigationDestination(isPresented: $navigateToVideo) {
                        if let id = sharedVideoId {
                            ResultsView(videoId: id)
                        }
                    }
            }
            .onOpenURL { url in
                if url.scheme == "tripclip",
                   let id = Int(url.lastPathComponent) {
                    sharedVideoId = id
                    navigateToVideo = true
                }
            }
        }
    }
}
