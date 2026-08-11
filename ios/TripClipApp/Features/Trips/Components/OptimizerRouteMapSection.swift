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
    /// Kullanıcı haritadaki Araba/Yürüyüş seçiciye dokunup modu
    /// DEĞİŞTİRDİĞİNDE üst katmana bildirir — bkz. docs/ios-trip-optimizer.md
    /// "Persistent Optimizer Transport Mode Sync". Bu bölüm bilerek
    /// `OptimizerConfigurationStore`'un VARLIĞINI bile bilmiyor (mimari
    /// kısıt: "the map component should not know about
    /// OptimizerConfigurationStore") — yalnızca `onStopSelectedFromMap` ile
    /// AYNI şekilde, ham bir kapanışla dışarı bir olay raporluyor;
    /// kalıcılık kararını (nereye/nasıl kaydedileceğini) TAMAMEN çağırana
    /// (`TripOptimizerView`) bırakıyor.
    var onTransportModeChanged: ((OptimizerTransportMode) -> Void)? = nil
    /// Gerçek yol rotalarını hesaplayan/önbelleğe alan/iptal eden
    /// asenkron katman — bkz. `OptimizerRouteCalculator`. Bu bölüm onu
    /// SAHİPLENİYOR (SwiftUI `@State`); `OptimizerRouteMap` yalnızca
    /// çıktısını (`calculator.routes`) düz bir prop olarak alır.
    ///
    /// `init`'te, çağıran tarafın (`TripOptimizerView`) enjekte ettiği
    /// EKRAN ÖMRÜNÜ AŞAN paylaşılan `OptimizerRouteCache` ile kuruluyor
    /// (bkz. `routeCache` init parametresi) — `@Environment` doğrudan
    /// burada okunmuyor, çünkü SwiftUI ortam değerleri bir View'ın kendi
    /// `init`'i çalışırken henüz enjekte edilmemiş olur (yalnızca `body`
    /// değerlendirilirken hazır); `@State`'in başlangıç değerini `init`
    /// içinde kurmak zorunda olduğumuzdan (bu dosyanın zaten yaptığı gibi,
    /// `_selection` için), paylaşılan önbelleğin bir `init` PARAMETRESİ
    /// olarak akması gerekiyor — bkz. docs/ios-trip-optimizer.md
    /// "Persistent Optimizer Route Cache".
    @State private var calculator: OptimizerRouteCalculator
    /// Kullanıcının seçtiği rota GÖSTERİM tercihi (Araba/Yürüyüş) — bkz.
    /// `OptimizerTransportMode`, docs/ios-trip-optimizer.md "Optimizer
    /// Route Transport Mode". Bilerek yalnızca yerel `@State`: `selection`
    /// (`OptimizerSelection`) gibi `TripOptimizerView`'la PAYLAŞILMIYOR —
    /// mod bir gün/durak KİMLİĞİ değil, salt bu bölümün kendi gösterim
    /// tercihi. Başlangıç değeri artık `init`'in `initialTransportMode`
    /// parametresinden gelir (bkz. aşağıda) — Persistent Optimizer
    /// Configuration milestone'undan itibaren bu, çağıranın (`TripOptimizerView`)
    /// `OptimizerConfigurationStore`'dan okuduğu, o trip için EN SON
    /// kullanılan modu yansıtabilir; hâlâ salt bu bölümün kendi yerel
    /// state'i — bu tip HÂLÂ `OptimizerConfigurationStore`'un varlığını
    /// bilmiyor. Persistent Optimizer Transport Mode Sync milestone'undan
    /// itibaren: kullanıcı burada modu DEĞİŞTİRDİĞİNDE bu artık
    /// `onTransportModeChanged` callback'i ile üst katmana (`TripOptimizerView`)
    /// RAPORLANIR — kalıcılık kararı orada verilir, burada değil (bkz. o
    /// callback'in kendi doc yorumu, docs "Persistent Optimizer Transport
    /// Mode Sync").
    @State private var selectedTransportMode: OptimizerTransportMode

    init(
        itinerary: Itinerary, selection: Binding<OptimizerSelection>, routeCache: OptimizerRouteCache,
        initialTransportMode: OptimizerTransportMode = .automobile,
        onStopSelectedFromMap: ((OptimizerMapStop) -> Void)? = nil,
        onTransportModeChanged: ((OptimizerTransportMode) -> Void)? = nil
    ) {
        self.mapData = OptimizerRouteMapData(itinerary: itinerary)
        self._selection = selection
        self.onStopSelectedFromMap = onStopSelectedFromMap
        self.onTransportModeChanged = onTransportModeChanged
        self._calculator = State(initialValue: OptimizerRouteCalculator(cache: routeCache))
        self._selectedTransportMode = State(initialValue: initialTransportMode)
    }

    var body: some View {
        if !mapData.isEmpty {
            VStack(alignment: .leading, spacing: 10) {
                if mapData.hasMultipleDays {
                    daySelector
                }

                transportModeSelector

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
            // Taşıma modu değiştiğinde AYNI günün rotasını, yeni mod için
            // yeniden hesapla — ayrı bir `.task(id:)`, `selection.dayIndex`
            // ile BİRLEŞTİRİLMİYOR (SwiftUI `task(id:)` yalnızca tek bir
            // `Equatable` değer alır, bir tuple bu protokole uyamaz), bu
            // yüzden iki bağımsız `.task` — biri gün, biri mod değişince
            // tetikleniyor, ikisi de aynı `loadVisibleDayRoutes()`'u
            // çağırıyor. `calculator.load` zaten aynı gün+mod için
            // idempotent (in-flight/önbellek kontrolü), bu yüzden ilk
            // görünüşte ikisinin de tetiklenmesi güvenli, gereksiz bir
            // istek YARATMAZ.
            .task(id: selectedTransportMode) { loadVisibleDayRoutes() }
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
            calculator.load(day: day, mode: selectedTransportMode)
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
                dayChip(
                    title: "Tümü", accessibilityLabel: "Tümü, tüm günler",
                    isSelected: selection.dayIndex == nil
                ) {
                    // Bir gün çipine doğrudan dokunmak, önceki bir durak
                    // odağını bilerek TEMİZLER — bu artık "belirli bir
                    // durağa odaklanma" değil, genel gün gezinme eylemi.
                    selection = OptimizerSelection(dayIndex: nil, stopID: nil)
                }
                ForEach(mapData.days) { day in
                    // `chipLabel` tarih varsa "12 Ağustos" (yıl yok, dar
                    // alan), yoksa "N. Gün" döner — Req 2 geriye dönük
                    // uyumluluk (bkz. OptimizerRouteMapData.swift). Gün
                    // seçim KİMLİĞİ hâlâ yalnızca `day.dayIndex` — tarih
                    // salt gösterim, `OptimizerSelection`'a hiç girmiyor
                    // (Req 3).
                    dayChip(
                        title: day.chipLabel, accessibilityLabel: day.chipAccessibilityLabel,
                        isSelected: selection.dayIndex == day.dayIndex
                    ) {
                        selection = OptimizerSelection(dayIndex: day.dayIndex, stopID: nil)
                    }
                }
            }
        }
    }

    private func dayChip(
        title: String, accessibilityLabel: String, isSelected: Bool, systemImage: String? = nil,
        action: @escaping () -> Void
    ) -> some View {
        Button {
            withAnimation(.easeOut(duration: 0.15)) { action() }
        } label: {
            HStack(spacing: 4) {
                if let systemImage {
                    Image(systemName: systemImage)
                        .font(.system(size: 12, weight: .semibold))
                }
                Text(title)
                    .font(.system(size: 13, weight: .semibold))
            }
            .foregroundStyle(isSelected ? AppColors.onAccent : AppColors.textSecondary)
            .padding(.horizontal, 14)
            .padding(.vertical, 8)
            .background(isSelected ? AppColors.accent : AppColors.surface2)
            .clipShape(Capsule())
        }
        .buttonStyle(PressableButtonStyle())
        // Req 7: görünen kısa metin ("12 Ağustos") yeterince açık olmayabilir
        // — VoiceOver etiketi gün numarasını da ekliyor, seçili durumu ayrı
        // bir "seçili" ipucu olarak taşıyor (yalnızca metne gömülü değil).
        .accessibilityLabel(accessibilityLabel)
        .accessibilityAddTraits(isSelected ? [.isSelected] : [])
    }

    // MARK: - Transport mode selector

    /// Kompakt Araba/Yürüyüş/Toplu Taşıma seçici — gün seçiciyle AYNI
    /// görsel dil (`dayChip`'i tekrar kullanır, yeni bir bileşen İCAT
    /// EDİLMEDİ). `OptimizerTransportMode.allCases` üzerinden jenerik
    /// olarak üretilir — yeni bir mod eklenince (Transit Transport Mode
    /// milestone'unda olduğu gibi) burada HİÇBİR değişiklik gerekmez.
    /// Üç seçenekle (v18'den itibaren) dar cihazlarda sıkışabileceğinden
    /// `daySelector`'la AYNI yatay `ScrollView` sarmalayıcısına alındı —
    /// önceki (yalnızca 2 seçenekli) sabit `HStack` varsayımı artık
    /// geçerli değil.
    private var transportModeSelector: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 8) {
                ForEach(OptimizerTransportMode.allCases, id: \.self) { mode in
                    dayChip(
                        title: mode.title, accessibilityLabel: mode.accessibilityLabel,
                        isSelected: selectedTransportMode == mode, systemImage: mode.symbolName
                    ) {
                        selectedTransportMode = mode
                        // Req "map mode change must flow back to the owning
                        // screen": ham olayı, kalıcılık kararı olmadan raporla
                        // — bkz. `onTransportModeChanged` doc yorumu.
                        onTransportModeChanged?(mode)
                    }
                }
            }
        }
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
