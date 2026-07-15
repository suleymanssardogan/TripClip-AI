import SwiftUI

@main
struct TripClipApp: App {

    @UIApplicationDelegateAdaptor(AppDelegate.self) private var appDelegate

    @State private var auth = AuthEnvironment()
    private let persistence = PersistenceController.shared

    var body: some Scene {
        WindowGroup {
            RootView()
                .environment(auth)
                .environment(\.managedObjectContext, persistence.context)
                .preferredColorScheme(.dark)
        }
    }
}
