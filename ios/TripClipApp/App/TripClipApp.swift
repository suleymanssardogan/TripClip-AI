import SwiftUI

@main
struct TripClipApp: App {

    @UIApplicationDelegateAdaptor(AppDelegate.self) private var appDelegate

    @State private var auth = AuthEnvironment()
    /// Uygulama oturumu boyunca yaşayan, ekran ömrünü aşan paylaşılan
    /// optimizer rota önbelleği — `AuthEnvironment` ile AYNI DI deseni
    /// (burada bir kez oluşturulup `.environment()` ile enjekte edilir,
    /// bir global singleton İCAT EDİLMİYOR). Bkz.
    /// docs/ios-trip-optimizer.md "Persistent Optimizer Route Cache".
    @State private var optimizerRouteCache = OptimizerRouteCache()
    /// Uygulama oturumu boyunca yaşayan, ekran ömrünü aşan paylaşılan
    /// optimizer gün/durak seçimi önbelleği — `optimizerRouteCache` ile
    /// AYNI DI deseni. Bkz. docs/ios-trip-optimizer.md "Persistent
    /// Optimizer Map Selection".
    @State private var optimizerSelectionStore = OptimizerSelectionStore()
    /// Uygulama oturumu boyunca yaşayan, ekran ömrünü aşan, trip-bazlı
    /// paylaşılan optimizer YAPILANDIRMASI önbelleği (yer seçimi, süre,
    /// saat, tarih, taşıma modu) — diğer ikisiyle AYNI DI deseni. Bkz.
    /// docs/ios-trip-optimizer.md "Persistent Optimizer Configuration".
    @State private var optimizerConfigurationStore = OptimizerConfigurationStore()
    private let persistence = PersistenceController.shared

    var body: some Scene {
        WindowGroup {
            RootView()
                .environment(auth)
                .environment(optimizerRouteCache)
                .environment(optimizerSelectionStore)
                .environment(optimizerConfigurationStore)
                .environment(\.managedObjectContext, persistence.context)
        }
    }
}
