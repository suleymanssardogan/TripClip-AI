import SwiftUI

/// AI Trip Optimizer — bir Trip için üretilmiş itinerary'lerin geçmişi.
/// TripsListView ile aynı liste-ekranı deseni (yükleme/hata/boş/liste
/// dörtlüsü, PressableButtonStyle + NavigationLink satırları). Bir satıra
/// dokunmak, itinerary'i TripOptimizerView'da `.viewSaved` modunda açar —
/// optimizer TEKRAR ÇALIŞTIRILMAZ, yalnızca kayıtlı sonuç yüklenir.
struct ItineraryHistoryView: View {

    let tripID: Int

    @Environment(AuthEnvironment.self) private var auth
    @State private var vm = ItineraryHistoryViewModel()

    var body: some View {
        ZStack {
            AppColors.background.ignoresSafeArea()

            if vm.isLoading && vm.itineraries.isEmpty {
                ProgressView().tint(AppColors.accentText)
            } else if let error = vm.error, vm.itineraries.isEmpty {
                errorState(error)
            } else if vm.itineraries.isEmpty {
                emptyState
            } else {
                list
            }
        }
        .navigationTitle("Optimizasyon Geçmişi")
        .navigationBarTitleDisplayMode(.inline)
        .task { await vm.load(tripID: tripID, auth: auth) }
        .refreshable { await vm.load(tripID: tripID, auth: auth) }
    }

    private var list: some View {
        ScrollView {
            LazyVStack(spacing: 10) {
                ForEach(vm.itineraries) { summary in
                    NavigationLink(destination: TripOptimizerView(mode: .viewSaved(itineraryID: summary.id))) {
                        ItineraryHistoryRowView(summary: summary)
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
            Image(systemName: "clock.arrow.circlepath")
                .font(.system(size: 52))
                .foregroundStyle(AppColors.textTertiary)
            Text("Henüz optimizasyon geçmişi yok")
                .font(.system(size: 18, weight: .semibold))
                .foregroundStyle(AppColors.text)
            Text("\"Optimize Et\" ile ilk itinerary'ini oluştur,\nburada saklanır.")
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
            Button("Tekrar Dene") { Task { await vm.load(tripID: tripID, auth: auth) } }
                .foregroundStyle(AppColors.accentText)
            Spacer()
        }
    }
}
