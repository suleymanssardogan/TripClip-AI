import SwiftUI

/// AI Trip Optimizer'ı çalıştırmadan ÖNCE gösterilen yapılandırma ekranı —
/// kullanıcı hangi mekanların optimize edileceğini ve kaç güne
/// yayılacağını seçer, ardından "Optimize Et" gerçek isteği gönderir.
///
/// Yalnızca `TripDetailView`'ın "sparkles" (Optimize Et) girişinden
/// ulaşılır — Itinerary History'den açılan `.viewSaved` akışı bu ekranı
/// HİÇ görmez, kayıtlı bir itinerary'i doğrudan yükler (bkz.
/// `ItineraryHistoryView`, değiştirilmedi — spesifikasyonun 7.
/// gereksinimi: "Opening a saved itinerary must continue to load it
/// directly").
struct TripOptimizerConfigView: View {

    let tripID: Int
    var onApplied: (() -> Void)? = nil

    @State private var vm: TripOptimizerConfigViewModel
    @Environment(\.dismiss) private var dismiss

    init(tripID: Int, stops: [TripStop], onApplied: (() -> Void)? = nil) {
        self.tripID = tripID
        self.onApplied = onApplied
        _vm = State(initialValue: TripOptimizerConfigViewModel(stops: stops))
    }

    var body: some View {
        ZStack(alignment: .bottom) {
            AppColors.background.ignoresSafeArea()

            ScrollView {
                VStack(alignment: .leading, spacing: 24) {
                    placesSection
                    durationSection
                    Color.clear.frame(height: 72)  // alttaki sabit çubuğa yer aç
                }
                .padding(.top, 16)
            }

            optimizeBar
        }
        .navigationTitle("Optimizasyonu Yapılandır")
        .navigationBarTitleDisplayMode(.inline)
    }

    // MARK: - Places

    private var placesSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("Mekanlar (\(vm.selectedCount)/\(vm.stops.count) seçili)")
                    .font(.system(size: 14, weight: .semibold))
                    .foregroundStyle(AppColors.textSecondary)
                    .textCase(.uppercase)
                    .tracking(0.8)

                Spacer()

                Button(vm.selectedCount == vm.stops.count ? "Seçimi Kaldır" : "Tümünü Seç") {
                    withAnimation(.easeOut(duration: 0.15)) {
                        if vm.selectedCount == vm.stops.count {
                            vm.deselectAll()
                        } else {
                            vm.selectAll()
                        }
                    }
                }
                .font(.system(size: 13, weight: .semibold))
                .foregroundStyle(AppColors.accentText)
            }
            .padding(.horizontal, 16)

            VStack(spacing: 8) {
                ForEach(vm.stops, id: \.placeId) { stop in
                    Button {
                        withAnimation(.easeOut(duration: 0.15)) {
                            vm.toggle(stop.placeId)
                        }
                    } label: {
                        TripStopSelectionRow(stop: stop, isSelected: vm.isSelected(stop.placeId))
                    }
                    .buttonStyle(PressableButtonStyle())
                }
            }
            .padding(.horizontal, 16)
        }
    }

    // MARK: - Duration

    private var durationSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Kaç Gün?")
                .font(.system(size: 14, weight: .semibold))
                .foregroundStyle(AppColors.textSecondary)
                .textCase(.uppercase)
                .tracking(0.8)
                .padding(.horizontal, 16)

            HStack(spacing: 16) {
                durationStepButton(systemImage: "minus", action: vm.decrementDuration)

                VStack(spacing: 2) {
                    Text(durationDisplayText)
                        .font(.system(size: 17, weight: .bold))
                        .foregroundStyle(AppColors.text)
                    Text(vm.durationDays == nil ? "gün sayısı kendiliğinden hesaplanır" : "gün")
                        .font(.system(size: 11))
                        .foregroundStyle(AppColors.textSecondary)
                }
                .frame(maxWidth: .infinity)

                durationStepButton(systemImage: "plus", action: vm.incrementDuration)
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 14)
            .background(AppColors.surface)
            .clipShape(RoundedRectangle(cornerRadius: 16))
            .overlay(RoundedRectangle(cornerRadius: 16).stroke(AppColors.border, lineWidth: 1))
            .padding(.horizontal, 16)
        }
    }

    private var durationDisplayText: String {
        guard let days = vm.durationDays else { return "Otomatik" }
        return "\(days)"
    }

    private func durationStepButton(systemImage: String, action: @escaping () -> Void) -> some View {
        Button(action: {
            withAnimation(.easeOut(duration: 0.15)) { action() }
        }) {
            Image(systemName: systemImage)
                .font(.system(size: 15, weight: .bold))
                .foregroundStyle(AppColors.text)
                .frame(width: 36, height: 36)
                .background(AppColors.surface2)
                .clipShape(Circle())
        }
        .buttonStyle(PressableButtonStyle())
    }

    // MARK: - Optimize CTA

    private var optimizeBar: some View {
        HStack {
            Text(vm.canOptimize ? "\(vm.selectedCount) mekan seçildi" : "En az bir mekan seçmelisin")
                .font(.system(size: 14, weight: .semibold))
                .foregroundStyle(vm.canOptimize ? AppColors.text : AppColors.destructive)

            Spacer()

            NavigationLink(
                destination: TripOptimizerView(
                    mode: .generate(
                        tripID: tripID,
                        placeIDs: vm.selectedPlaceIDsInTripOrder,
                        durationDays: vm.durationDays
                    ),
                    onApplied: onApplied
                )
            ) {
                Text("Optimize Et")
                    .font(.system(size: 14, weight: .bold))
                    .padding(.horizontal, 16)
                    .padding(.vertical, 10)
                    .background(vm.canOptimize ? AppColors.accent : AppColors.surface2)
                    .foregroundStyle(vm.canOptimize ? Color.white : AppColors.textTertiary)
                    .clipShape(Capsule())
            }
            .disabled(!vm.canOptimize)
        }
        .padding(.horizontal, 20)
        .padding(.vertical, 14)
        .background(.ultraThinMaterial)
        .clipShape(RoundedRectangle(cornerRadius: 20))
        .overlay(RoundedRectangle(cornerRadius: 20).stroke(AppColors.border, lineWidth: 1))
        .padding(.horizontal, 16)
        .padding(.bottom, 12)
    }
}
