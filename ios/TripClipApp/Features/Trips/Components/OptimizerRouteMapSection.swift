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
///
/// Gün + durak seçimi artık BURADA SAHİPLENİLMİYOR — `TripOptimizerView`'ın
/// itinerary listesiyle PAYLAŞTIĞI tek `OptimizerSelection` üzerinden bir
/// `Binding` olarak alınıyor (Req 13 "the map should receive the selection
/// rather than inventing its own authoritative state").
struct OptimizerRouteMapSection: View {

    private let mapData: OptimizerRouteMapData
    @Binding private var selection: OptimizerSelection
    /// Kullanıcı haritada bir pine dokunduğunda üst katmana (yalnızca
    /// kaydırma/görünürlük yan etkisi için — state güncellemesi zaten
    /// `selection` binding'i üzerinden burada yapılıyor) bildirir. Bkz.
    /// `TripOptimizerView`: itinerary listesindeki ilgili satıra kaydırır.
    var onStopSelectedFromMap: ((OptimizerMapStop) -> Void)? = nil
    /// Gerçek yol rotalarını hesaplayan/önbelleğe alan/iptal eden
    /// asenkron katman — bkz. `OptimizerRouteCalculator`. Bu bölüm onu
    /// SAHİPLENİYOR (SwiftUI `@State`); `OptimizerRouteMap` yalnızca
    /// çıktısını (`calculator.routes`) düz bir prop olarak alır.
    @State private var calculator = OptimizerRouteCalculator()

    init(
        itinerary: Itinerary, selection: Binding<OptimizerSelection>,
        onStopSelectedFromMap: ((OptimizerMapStop) -> Void)? = nil
    ) {
        self.mapData = OptimizerRouteMapData(itinerary: itinerary)
        self._selection = selection
        self.onStopSelectedFromMap = onStopSelectedFromMap
    }

    var body: some View {
        if !mapData.isEmpty {
            VStack(alignment: .leading, spacing: 10) {
                if mapData.hasMultipleDays {
                    daySelector
                }

                ZStack(alignment: .topTrailing) {
                    OptimizerRouteMap(
                        data: mapData, selectedDayIndex: selection.dayIndex,
                        dayRoutes: calculator.routes,
                        selectedStopID: selection.stopID,
                        onSelectStop: { stop in
                            // Req 2 "Map → Itinerary": tek gerçek kaynak olan
                            // paylaşılan seçimi güncelle — Req 1/4 kuralı
                            // burada da geçerli (aynı kural, `focusing`).
                            selection = .focusing(dayIndex: stop.dayIndex, stopID: stop.id)
                            onStopSelectedFromMap?(stop)
                        }
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
            // Gün seçimi GERÇEKTEN değiştiğinde (ve ilk görünüşte) o an
            // görünür günlerin rotasını hesapla — yalnızca `dayIndex`'i
            // izler, `selection`'ın tamamını DEĞİL: bir durak seçimi aynı
            // günde kalıyorsa bu `.task` YENİDEN TETİKLENMEZ (Req 1 "do not
            // recalculate the route merely because a stop was selected").
            // `calculator.load` zaten önbellek/in-flight kontrolüyle
            // gereksiz isteği önlüyor (Req 6, Req 9).
            .task(id: selection.dayIndex) { loadVisibleDayRoutes() }
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
        for day in mapData.visibleDays(selectedDayIndex: selection.dayIndex) {
            calculator.load(day: day)
        }
    }

    private var isCalculatingVisibleRoute: Bool {
        mapData.visibleDays(selectedDayIndex: selection.dayIndex)
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
                dayChip(title: "Tümü", isSelected: selection.dayIndex == nil) {
                    // Bir gün çipine doğrudan dokunmak, önceki bir durak
                    // odağını bilerek TEMİZLER — bu artık "belirli bir
                    // durağa odaklanma" değil, genel gün gezinme eylemi.
                    selection = OptimizerSelection(dayIndex: nil, stopID: nil)
                }
                ForEach(mapData.days) { day in
                    dayChip(title: "\(day.dayIndex + 1). Gün", isSelected: selection.dayIndex == day.dayIndex) {
                        selection = OptimizerSelection(dayIndex: day.dayIndex, stopID: nil)
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
