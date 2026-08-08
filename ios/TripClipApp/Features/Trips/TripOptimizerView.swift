import SwiftUI

/// AI Trip Optimizer sonuç ekranı — iki modda çalışır, ikisi de aynı
/// yükleme/hata/boş/başarı sunumunu paylaşır (itinerary render mantığı hiçbir
/// yerde tekrarlanmaz):
///   - `.generate`: Trip'in mevcut duraklarından YENİ bir itinerary üretir.
///   - `.viewSaved`: Itinerary History'den açılan, ZATEN üretilmiş kayıtlı
///     bir itinerary'i olduğu gibi yükler — optimizer TEKRAR ÇALIŞMAZ.
///
/// Yalnızca ÖNİZLEME: Trip'in kendi TripStop'unu hiçbir zaman değiştirmez
/// (backend zaten TripItinerary'i ayrı bir kayıt olarak persist ediyor —
/// bkz. docs/trip-optimizer.md "Architecture: neden TripStop'a yazılmıyor").
/// "Kapat" ve "Daha Sonra İçin Kaydet" bu yüzden sunucu tarafında aynı sonucu
/// üretir; aralarındaki fark yalnızca kullanıcıya verilen geri bildirimdir —
/// yalnızca `.generate` modunda gösterilir, `.viewSaved` zaten geçmişten
/// açıldığı için "kaydet"in bir anlamı yok (bkz. docs/ios-trip-optimizer.md).
struct TripOptimizerView: View {

    enum Mode {
        case generate(tripID: Int, placeIDs: [Int])
        case viewSaved(itineraryID: Int)
    }

    let mode: Mode

    @Environment(AuthEnvironment.self) private var auth
    @Environment(\.dismiss) private var dismiss
    @State private var vm = TripOptimizerViewModel()
    @State private var showSavedConfirmation = false

    private var navigationTitle: String {
        switch mode {
        case .generate:  return "Gezi Optimizasyonu"
        case .viewSaved: return "Kayıtlı İtinerary"
        }
    }

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
        .navigationTitle(navigationTitle)
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .navigationBarLeading) {
                Button("Kapat") { dismiss() }
                    .foregroundStyle(AppColors.textSecondary)
            }
        }
        .task { await load() }
        .alert("Kaydedildi", isPresented: $showSavedConfirmation) {
            Button("Tamam") { dismiss() }
        } message: {
            Text("Bu itinerary geziye kaydedildi. Gezinin kendisi değişmedi — istediğin zaman tekrar optimize edebilirsin.")
        }
    }

    private func load() async {
        switch mode {
        case .generate(let tripID, let placeIDs):
            await vm.optimize(tripID: tripID, placeIDs: placeIDs, auth: auth)
        case .viewSaved(let itineraryID):
            await vm.loadItinerary(itineraryID: itineraryID, auth: auth)
        }
    }

    // MARK: - States

    private var loadingState: some View {
        VStack(spacing: 16) {
            ProgressView().tint(AppColors.accentText)
            Text(loadingMessage)
                .font(.system(size: 14))
                .foregroundStyle(AppColors.textSecondary)
        }
    }

    private var loadingMessage: String {
        switch mode {
        case .generate:  return "Gezi optimize ediliyor…"
        case .viewSaved: return "İtinerary yükleniyor…"
        }
    }

    private func errorState(_ error: APIError) -> some View {
        VStack(spacing: 16) {
            Image(systemName: "exclamationmark.triangle")
                .font(.system(size: 48))
                .foregroundStyle(AppColors.destructive)
            Text(error.localizedDescription ?? "Yüklenemedi.")
                .foregroundStyle(AppColors.textSecondary)
                .multilineTextAlignment(.center)
                .padding(.horizontal, 40)
            Button("Tekrar Dene") {
                Task { await load() }
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

                if case .generate = mode {
                    footerButton
                        .padding(.top, 8)
                }

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
