import SwiftUI

struct RootView: View {

    @Environment(AuthEnvironment.self) private var auth

    var body: some View {
        if auth.isAuthenticated {
            TabView {
                HomeView()
                    .tabItem { Label("Ana Sayfa", systemImage: "house") }

                NavigationStack {
                    LibraryView()
                }
                .tabItem { Label("Mekanlar", systemImage: "mappin.and.ellipse") }

                NavigationStack {
                    TripsListView()
                }
                .tabItem { Label("Geziler", systemImage: "map") }
            }
            .tint(AppColors.accent)
        } else {
            WelcomeView()
        }
    }
}
