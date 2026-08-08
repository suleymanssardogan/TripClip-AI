import SwiftUI

/// AI Trip Optimizer önizleme ekranı — bir Trip'in mevcut duraklarından
/// üretilen çok-günlü itinerary'i gösterir. Yalnızca ÖNİZLEME: Trip'in kendi
/// TripStop'unu hiçbir zaman değiştirmez (backend zaten TripItinerary'i ayrı
/// bir kayıt olarak persist ediyor — bkz. docs/trip-optimizer.md
/// "Architecture: neden TripStop'a yazılmıyor"). "Kapat" ve "Daha Sonra İçin
/// Kaydet" bu yüzden sunucu tarafında aynı sonucu üretir; aralarındaki fark
/// yalnızca kullanıcıya verilen geri bildirimdir — bkz. docs/ios-trip-optimizer.md.
struct TripOptimizerView: View {

    let tripID:   Int
    let placeIDs: [Int]

    @Environment(AuthEnvironment.self) private var auth
    @Environment(\.dismiss) private var dismiss
    @State private var vm = TripOptimizerViewModel()
    @State private var showSavedConfirmation = false

    var body: some View {
        ZStack {
            AppColors.background.ignoresSafeArea()

            if vm.isLoading {
                loadingState
            } else if let error = vm.error {
                errorState(error)
            } else if let itinerary = vm.itinerary {
                if itinerary.days.flatMap(\.stops).isEmpty {
                    emptyState
                } else {
                    resultContent(itinerary)
                }
            }
        }
        .navigationTitle("Gezi Optimizasyonu")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .navigationBarLeading) {
                Button("Kapat") { dismiss() }
                    .foregroundStyle(AppColors.textSecondary)
            }
        }
        .task { await vm.optimize(tripID: tripID, placeIDs: placeIDs, auth: auth) }
        .alert("Kaydedildi", isPresented: $showSavedConfirmation) {
            Button("Tamam") { dismiss() }
        } message: {
            Text("Bu itinerary geziye kaydedildi. Gezinin kendisi değişmedi — istediğin zaman tekrar optimize edebilirsin.")
        }
    }

    // MARK: - States

    private var loadingState: some View {
        VStack(spacing: 16) {
            ProgressView().tint(AppColors.accentText)
            Text("Gezi optimize ediliyor…")
                .font(.system(size: 14))
                .foregroundStyle(AppColors.textSecondary)
        }
    }

    private func errorState(_ error: APIError) -> some View {
        VStack(spacing: 16) {
            Image(systemName: "exclamationmark.triangle")
                .font(.system(size: 48))
                .foregroundStyle(AppColors.destructive)
            Text(error.localizedDescription ?? "Optimize edilemedi.")
                .foregroundStyle(AppColors.textSecondary)
                .multilineTextAlignment(.center)
                .padding(.horizontal, 40)
            Button("Tekrar Dene") {
                Task { await vm.optimize(tripID: tripID, placeIDs: placeIDs, auth: auth) }
            }
            .foregroundStyle(AppColors.accentText)
        }
    }

    private var emptyState: some View {
        VStack(spacing: 12) {
            Image(systemName: "mappin.slash")
                .font(.system(size: 48))
                .foregroundStyle(AppColors.textTertiary)
            Text("Optimize edilecek durak bulunamadı")
                .font(.system(size: 15, weight: .semibold))
                .foregroundStyle(AppColors.text)
        }
    }

    // MARK: - Result

    @ViewBuilder
    private func resultContent(_ itinerary: Itinerary) -> some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                OptimizerScoreBadge(
                    score: itinerary.optimizationScore,
                    totalDistanceKm: itinerary.totalDistanceKm,
                    totalTravelMinutes: itinerary.totalTravelTimeMinutes
                )

                if !itinerary.warnings.isEmpty {
                    ItineraryWarningsSection(warnings: itinerary.warnings)
                }

                ForEach(itinerary.days) { day in
                    ItineraryDaySection(day: day)
                }

                footerButton
                    .padding(.top, 8)

                Color.clear.frame(height: 24)
            }
            .padding(.horizontal, 16)
            .padding(.top, 16)
        }
    }

    private var footerButton: some View {
        Button {
            showSavedConfirmation = true
        } label: {
            Text("Daha Sonra İçin Kaydet")
                .font(.system(size: 15, weight: .bold))
                .foregroundStyle(AppColors.onAccent)
                .frame(maxWidth: .infinity)
                .padding(.vertical, 14)
                .background(AppColors.accent)
                .clipShape(RoundedRectangle(cornerRadius: 14))
        }
    }
}
