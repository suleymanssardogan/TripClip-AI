import SwiftUI

struct TripsListView: View {

    @Environment(AuthEnvironment.self) private var auth
    @State private var vm = TripsListViewModel()
    /// `.task` yalnızca BİR KEZ çalışır (view kimliği boyunca) — bu liste bir
    /// trip'e girip (silme/durak düzenleme yapıp) geri dönüldüğünde YENİDEN
    /// tetiklenmez, bu yüzden silinen bir trip'in satırı listede KALIR ve
    /// durak sayısı bayatlar. `HomeView`'in KENDİ AYNI sorunu için kullandığı
    /// `.onChange(of: navPath.count)` çözümü burada uygulanamaz (bu ekran
    /// kendi `NavigationStack`'ini sahiplenmiyor, `LibraryView`'ın stack'ine
    /// bir `NavigationLink` hedefi olarak push ediliyor) — bunun yerine
    /// `.onAppear`, pushed bir child'dan geri dönüldüğünde de güvenilir
    /// biçimde tetiklenen daha genel sinyal (M35 audit bulgusu).
    @State private var hasAppearedOnce = false

    var body: some View {
        ZStack {
            AppColors.background.ignoresSafeArea()

            if vm.isLoading && vm.trips.isEmpty {
                ProgressView().tint(AppColors.accentText)
                    .accessibilityLabel("Yükleniyor")
            } else if let error = vm.error, vm.trips.isEmpty {
                errorState(error)
            } else if vm.trips.isEmpty {
                emptyState
            } else {
                list
            }
        }
        .navigationTitle("Gezilerim")
        .navigationBarTitleDisplayMode(.inline)
        .task { await vm.load(auth: auth) }
        .onAppear {
            if hasAppearedOnce {
                Task { await vm.load(auth: auth) }
            }
            hasAppearedOnce = true
        }
        .refreshable { await vm.load(auth: auth) }
    }

    private var list: some View {
        ScrollView {
            LazyVStack(spacing: 10) {
                ForEach(vm.trips) { trip in
                    NavigationLink(destination: TripDetailView(tripID: trip.id)) {
                        TripRowView(trip: trip)
                    }
                    .buttonStyle(PressableButtonStyle())
                }
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 12)
        }
    }

    private var emptyState: some View {
        VStack(spacing: 16) {
            Spacer()
            Image(systemName: "map")
                .font(.system(size: 52))
                .foregroundStyle(AppColors.textTertiary)
            Text("Henüz gezi oluşturmadın")
                .font(.system(size: 18, weight: .semibold))
                .foregroundStyle(AppColors.text)
            Text("Kütüphaneden mekan seçip\n\"Gezi Oluştur\" ile ilk rotanı yap.")
                .font(.system(size: 14))
                .foregroundStyle(AppColors.textSecondary)
                .multilineTextAlignment(.center)
            Spacer()
        }
        .padding(.horizontal, 32)
    }

    private func errorState(_ error: APIError) -> some View {
        VStack(spacing: 16) {
            Spacer()
            Image(systemName: "wifi.exclamationmark")
                .font(.system(size: 48))
                .foregroundStyle(AppColors.destructive)
            Text(error.localizedDescription ?? "Bir hata oluştu.")
                .font(.system(size: 15))
                .foregroundStyle(AppColors.textSecondary)
                .multilineTextAlignment(.center)
                .padding(.horizontal, 40)
            Button("Tekrar Dene") { Task { await vm.load(auth: auth) } }
                .foregroundStyle(AppColors.accentText)
            Spacer()
        }
    }
}
