import SwiftUI

/// `TripOptimizerView`'ın harita bölümü — `OptimizerRouteMapData` +
/// `OptimizerRouteMap`'i birleştirip gün seçici ve eksik-koordinat uyarısını
/// ekler. `TripOptimizerView` bu türü tek bir satırla kullanır, itinerary'i
/// haritaya dönüştürme mantığı burada tekrarlanmadan tek bir yerde kalır.
///
/// `mapData` bir kez, `init`'te hesaplanır — `itinerary` ekran ömrü boyunca
/// değişmediğinden (bkz. `TripOptimizerViewModel`, sonuç yüklendikten sonra
/// yeniden atanmaz) her `body` değerlendirmesinde yeniden hesaplamak
/// (Req 9 "avoid unnecessary ... repeated annotation creation") gereksiz
/// olurdu.
struct OptimizerRouteMapSection: View {

    private let mapData: OptimizerRouteMapData
    @State private var selectedDayIndex: Int? = nil
    /// Gerçek yol rotalarını hesaplayan/önbelleğe alan/iptal eden
    /// asenkron katman — bkz. `OptimizerRouteCalculator`. Bu bölüm onu
    /// SAHİPLENİYOR (SwiftUI `@State`); `OptimizerRouteMap` yalnızca
    /// çıktısını (`calculator.routes`) düz bir prop olarak alır.
    @State private var calculator = OptimizerRouteCalculator()

    init(itinerary: Itinerary) {
        self.mapData = OptimizerRouteMapData(itinerary: itinerary)
    }

    var body: some View {
        if !mapData.isEmpty {
            VStack(alignment: .leading, spacing: 10) {
                if mapData.hasMultipleDays {
                    daySelector
                }

                ZStack(alignment: .topTrailing) {
                    OptimizerRouteMap(
                        data: mapData, selectedDayIndex: selectedDayIndex,
                        dayRoutes: calculator.routes
                    )
                    .frame(height: 260)
                    .clipShape(RoundedRectangle(cornerRadius: 20))

                    if isCalculatingVisibleRoute {
                        routeLoadingIndicator
                    }
                }

                if mapData.missingCoordinateCount > 0 {
                    missingCoordinateNotice
                }
            }
            // Gün seçimi değiştiğinde (ve ilk görünüşte) o an görünür
            // günlerin rotasını hesapla — `calculator.load` zaten önbellek/
            // in-flight kontrolüyle gereksiz isteği önlüyor (Req 6, Req 9).
            .task(id: selectedDayIndex) { loadVisibleDayRoutes() }
            // Ekrandan kaybolurken bekleyen hesaplamaları iptal et (Req 5
            // "view disappearance").
            .onDisappear { calculator.cancelAll() }
        } else if mapData.missingCoordinateCount > 0 {
            // Hiçbir durağın koordinatı yok — harita hiç çizilmiyor, ama
            // durum kullanıcıya sessizce değil açıkça bildiriliyor (Req 7).
            // Durakların kendisi ItineraryDaySection'da metinsel olarak
            // görünmeye devam eder, bu bölüm yalnızca haritayı etkiler.
            missingCoordinateNotice
        }
    }

    private func loadVisibleDayRoutes() {
        for day in mapData.visibleDays(selectedDayIndex: selectedDayIndex) {
            calculator.load(day: day)
        }
    }

    private var isCalculatingVisibleRoute: Bool {
        mapData.visibleDays(selectedDayIndex: selectedDayIndex)
            .contains { calculator.routes[$0.dayIndex]?.isLoading == true }
    }

    private var routeLoadingIndicator: some View {
        ProgressView()
            .controlSize(.small)
            .tint(AppColors.text)
            .padding(8)
            .background(.ultraThinMaterial, in: Circle())
            .padding(10)
    }

    // MARK: - Day selector

    private var daySelector: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 8) {
                dayChip(title: "Tümü", isSelected: selectedDayIndex == nil) {
                    selectedDayIndex = nil
                }
                ForEach(mapData.days) { day in
                    dayChip(title: "\(day.dayIndex + 1). Gün", isSelected: selectedDayIndex == day.dayIndex) {
                        selectedDayIndex = day.dayIndex
                    }
                }
            }
        }
    }

    private func dayChip(title: String, isSelected: Bool, action: @escaping () -> Void) -> some View {
        Button {
            withAnimation(.easeOut(duration: 0.15)) { action() }
        } label: {
            Text(title)
                .font(.system(size: 13, weight: .semibold))
                .foregroundStyle(isSelected ? AppColors.onAccent : AppColors.textSecondary)
                .padding(.horizontal, 14)
                .padding(.vertical, 8)
                .background(isSelected ? AppColors.accent : AppColors.surface2)
                .clipShape(Capsule())
        }
        .buttonStyle(PressableButtonStyle())
    }

    // MARK: - Missing coordinates

    private var missingCoordinateNotice: some View {
        HStack(spacing: 8) {
            Image(systemName: "exclamationmark.triangle")
                .font(.system(size: 12))
                .foregroundStyle(AppColors.textTertiary)
            Text(missingCoordinateText)
                .font(.system(size: 12))
                .foregroundStyle(AppColors.textSecondary)
        }
    }

    private var missingCoordinateText: String {
        mapData.missingCoordinateCount == 1
            ? "1 durağın konum bilgisi yok, haritada gösterilemiyor."
            : "\(mapData.missingCoordinateCount) durağın konum bilgisi yok, haritada gösterilemiyor."
    }
}
