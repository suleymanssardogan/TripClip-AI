import SwiftUI

struct RootView: View {

    @Environment(AuthEnvironment.self) private var auth

    var body: some View {
        if auth.isAuthenticated {
            HomeView()
        } else {
            WelcomeView()
        }
    }
}
