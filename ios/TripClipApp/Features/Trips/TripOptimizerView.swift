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
        /// `durationDays` nil ise (Optimizer Yapılandırma ekranında
        /// "Otomatik" seçiliyken) backend kendi gerekli gün sayısını türetir
        /// — bkz. TripOptimizerConfigViewModel.
        case generate(
            tripID: Int, placeIDs: [Int], durationDays: Int? = nil,
            preferredStartTime: ClockTime = .defaultStart, preferredEndTime: ClockTime = .defaultEnd,
            startDate: PlanningDate? = nil
        )
        case viewSaved(itineraryID: Int)
    }

    let mode: Mode
    /// Başarılı "Trip'e Uygula" sonrası çağrılır — çağıran taraf TripDetailView'i
    /// yeniden yükler (bkz. docs/ios-trip-optimizer.md "Apply to Trip").
    var onApplied: (() -> Void)? = nil

    @Environment(AuthEnvironment.self) private var auth
    /// Ekran ömrünü aşan, uygulama oturumu boyunca yaşayan paylaşılan rota
    /// önbelleği — `TripClipApp.swift`'te bir kez oluşturulup enjekte
    /// edilir (bkz. docs/ios-trip-optimizer.md "Persistent Optimizer Route
    /// Cache"). `OptimizerRouteMapSection`'a `init` parametresi olarak
    /// geçiriliyor (bkz. o dosyadaki doc yorumu — `@Environment`'ın orada
    /// doğrudan okunamama nedeni).
    @Environment(OptimizerRouteCache.self) private var routeCache
    /// Ekran ömrünü aşan, uygulama oturumu boyunca yaşayan paylaşılan
    /// gün/durak seçimi önbelleği — `routeCache` ile AYNI DI deseni. Bu
    /// View, önbelleğin KENDİ doğrulama/geri-getirme mantığını hiç bilmez
    /// — yalnızca `load()` içinde `resolveSelection(for:)`'u çağırıp
    /// sonucu kendi `selection` state'ine atar, ve `selection` her
    /// değiştiğinde (`onChange`) güncel değeri geri yazar. Bkz.
    /// docs/ios-trip-optimizer.md "Persistent Optimizer Map Selection".
    @Environment(OptimizerSelectionStore.self) private var selectionStore
    /// Ekran ömrünü aşan, uygulama oturumu boyunca yaşayan, trip-bazlı
    /// paylaşılan optimizer yapılandırma önbelleği. `itinerary.tripId` için
    /// kaydedilmiş SON taşıma modunu okuyup `OptimizerRouteMapSection`'ın
    /// başlangıç değerini tohumlamak için kullanılır (bkz. o dosyadaki
    /// `initialTransportMode` parametresi) — Persistent Optimizer
    /// Transport Mode Sync milestone'undan itibaren TERSİ yönde de akış
    /// var: harita kendi mod değişikliğini `onTransportModeChanged`
    /// callback'iyle raporlar, bu View de `configStore.updateTransportMode`'u
    /// çağırarak GERİ yazar (bkz. `resultContent`). Yapılandırma ekranının
    /// KENDİ state'inin (seçili mekanlar/süre/saat/tarih) geri kalanını
    /// hâlâ hiç bilmez/yazmaz — yalnızca `transportMode`, ve yalnızca
    /// `OptimizerConfigurationStore`'un kendi merkezi
    /// `updateTransportMode` metodu aracılığıyla. Bkz.
    /// docs/ios-trip-optimizer.md "Persistent Optimizer Configuration" ve
    /// "Persistent Optimizer Transport Mode Sync".
    @Environment(OptimizerConfigurationStore.self) private var configStore
    @Environment(\.dismiss) private var dismiss
    @State private var vm = TripOptimizerViewModel()
    @State private var showSavedConfirmation = false
    @State private var showApplyConfirm = false
    @State private var showApplySuccess = false
    /// Harita (`OptimizerRouteMapSection`) ve itinerary listesi
    /// (`ItineraryDaySection`) arasında PAYLAŞILAN tek seçim durumu — Req
    /// 13: ikisi de kendi otoriter kopyasını icat etmez, burada, tek bir
    /// yerde sahiplenilir. Değişmesi (ne map'ten ne itinerary'den) ASLA
    /// `vm.optimize`/`vm.loadItinerary`/`vm.applyToTrip`'i tetiklemez — bu
    /// state, o metotların hiçbirinden çağrılmaz (Req 5/6: seçim, ne yeni
    /// bir optimizasyon isteği ne apply ne de gereksiz bir rota
    /// hesaplaması başlatır).
    ///
    /// Persistent Optimizer Map Selection milestone'unda: `load()`
    /// tamamlanır tamamlanmaz `selectionStore.resolveSelection(for:)`
    /// sonucuyla başlatılır (bkz. `load()`), ardından HER değişikliğinde
    /// (`onChange`, aşağıda) o değer önbelleğe geri yazılır — yine de TEK
    /// gerçek kaynak bu — `OptimizerSelectionStore` yalnızca onun bir
    /// itinerary'e göre anahtarlanmış GEÇMİŞİNİ tutuyor, ikinci bir
    /// state modeli İCAT EDİLMEDİ.
    @State private var selection = OptimizerSelection()

    private static let mapAnchor = "optimizer-route-map"

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
        // Req 8 "user interaction must update the store": `selection`in
        // KAYNAĞI ne olursa olsun (gün çipi, harita durak dokunuşu,
        // itinerary satırı, ya da `load()`'ın kendi geri-yükleme ataması)
        // her değiştiğinde güncel değeri önbelleğe yazar — tek, merkezi
        // senkronizasyon noktası. `OptimizerRouteMapSection`/
        // `ItineraryDaySection`'ın HİÇBİRİ bu önbelleğin varlığını bilmez
        // (Req 2), yalnızca kendi payına düşen `selection` mutasyonlarını
        // yapmaya devam ederler. İlk (varsayılan) değer için TETİKLENMEZ
        // (`onChange`in kendi `initial: false` varsayılanı) — yalnızca
        // GERÇEK bir değişiklikte.
        .onChange(of: selection) { _, newSelection in
            if let itinerary = vm.itinerary {
                selectionStore.store(newSelection, for: itinerary.id)
            }
        }
        .alert("Kaydedildi", isPresented: $showSavedConfirmation) {
            Button("Tamam") { dismiss() }
        } message: {
            Text("Bu itinerary geziye kaydedildi. Gezinin kendisi değişmedi — istediğin zaman tekrar optimize edebilirsin.")
        }
        .confirmationDialog(
            "Bu itinerary Trip'e uygulansın mı?",
            isPresented: $showApplyConfirm,
            titleVisibility: .visible
        ) {
            Button("Uygula") {
                Task { await applyItinerary() }
            }
            Button("Vazgeç", role: .cancel) { }
        } message: {
            Text("Gezinin mevcut durak listesi bu itinerary ile değiştirilecek. Kayıtlı itinerary geçmişte kalır ve istediğin zaman tekrar uygulanabilir.")
        }
        .alert("Uygulandı", isPresented: $showApplySuccess) {
            Button("Tamam") {
                onApplied?()
                dismiss()
            }
        } message: {
            Text("Gezinin durak listesi bu itinerary ile güncellendi.")
        }
        .alert(
            "Uygulanamadı",
            isPresented: Binding(
                get: { vm.applyError != nil },
                set: { if !$0 { vm.applyError = nil } }
            )
        ) {
            Button("Tamam", role: .cancel) { vm.applyError = nil }
        } message: {
            Text(vm.applyError ?? "")
        }
    }

    private func applyItinerary() async {
        guard let itinerary = vm.itinerary else { return }
        let success = await vm.applyToTrip(itineraryID: itinerary.id, auth: auth)
        if success { showApplySuccess = true }
    }

    private func load() async {
        switch mode {
        case .generate(let tripID, let placeIDs, let durationDays, let preferredStartTime, let preferredEndTime, let startDate):
            await vm.optimize(
                tripID: tripID, placeIDs: placeIDs, durationDays: durationDays,
                preferredStartTime: preferredStartTime, preferredEndTime: preferredEndTime,
                startDate: startDate, auth: auth
            )
        case .viewSaved(let itineraryID):
            await vm.loadItinerary(itineraryID: itineraryID, auth: auth)
        }
        // Itinerary artık mevcutsa (Req 7 "selection restoration should
        // happen only after the Itinerary is available") — `vm.itinerary`
        // atandıktan HEMEN sonra, aynı senkron adımda, `resultContent`
        // hiç `nil`/`nil` ("Tümü") anlık görüntüsüyle çizilmeden ÖNCE
        // doğrulanmış seçimi kur. `await` YOK bu iki satır arasında, bu
        // yüzden SwiftUI'nin bir sonraki render'ı ikisini BİRLİKTE
        // yansıtır — geçici bir "Tümü" yanıp sönmesi (ve onun tetikleyeceği
        // gereksiz "tüm günleri yükle" isteği) engellenmiş olur.
        if let itinerary = vm.itinerary {
            selection = selectionStore.resolveSelection(for: itinerary)
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
        ScrollViewReader { proxy in
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                OptimizerRouteMapSection(
                    itinerary: itinerary,
                    selection: $selection,
                    routeCache: routeCache,
                    initialTransportMode: configStore.configuration(for: itinerary.tripId)?.transportMode ?? .automobile,
                    onStopSelectedFromMap: { stop in
                        // Req 2 "Map → Itinerary": itinerary listesini,
                        // haritada dokunulan durağın satırına kaydır —
                        // TripDetailView'in kendi mapAnchor/scrollTo
                        // desenindeki AYNI mekanizma, ters yönde.
                        withAnimation {
                            proxy.scrollTo(ItineraryDaySection.rowID(for: stop.id), anchor: .center)
                        }
                    },
                    onTransportModeChanged: { mode in
                        // Persistent Optimizer Transport Mode Sync: harita
                        // artık kendi mod değişikliğini buraya raporluyor —
                        // birleştirme/varsayılan mantığı (bu trip için
                        // yapılandırma ekranı hiç ziyaret edilmemiş olabilir,
                        // ör. Itinerary History'den doğrudan `.viewSaved`)
                        // TEK bir yerde, `OptimizerConfigurationStore`'un
                        // kendisinde yaşıyor — bkz. `updateTransportMode`.
                        configStore.updateTransportMode(
                            mode, for: itinerary.tripId,
                            fallbackSelectedPlaceIDs: Set(itinerary.days.flatMap(\.stops).compactMap(\.placeId))
                        )
                    }
                )
                .id(Self.mapAnchor)

                OptimizerScoreBadge(
                    score: itinerary.optimizationScore,
                    totalDistanceKm: itinerary.totalDistanceKm,
                    totalTravelMinutes: itinerary.totalTravelTimeMinutes
                )

                if !itinerary.warnings.isEmpty {
                    ItineraryWarningsSection(warnings: itinerary.warnings)
                }

                ForEach(itinerary.days) { day in
                    ItineraryDaySection(
                        day: day,
                        selectedStopID: selection.stopID,
                        onSelectStop: { stop in
                            // Req 1 "Itinerary → Map": paylaşılan seçimi
                            // güncelle (aynı `focusing` kuralı — Req 1/4)
                            // ve haritayı görünür kılmak için yukarı
                            // kaydır (TripDetailView'in LocationCard tıklama
                            // deseniyle AYNI: focus + scroll tek eylemde).
                            selection = .focusing(dayIndex: stop.dayIndex, stopID: stop.id)
                            withAnimation { proxy.scrollTo(Self.mapAnchor, anchor: .top) }
                        }
                    )
                }

                applyButton
                    .padding(.top, 8)

                if case .generate = mode {
                    footerButton
                }

                Color.clear.frame(height: 24)
            }
            .padding(.horizontal, 16)
            .padding(.top, 16)
        }
        }
    }

    private var footerButton: some View {
        Button {
            showSavedConfirmation = true
        } label: {
            Text("Daha Sonra İçin Kaydet")
                .font(.system(size: 15, weight: .bold))
                .foregroundStyle(AppColors.accentText)
                .frame(maxWidth: .infinity)
                .padding(.vertical, 14)
                .background(AppColors.accent.opacity(0.12))
                .clipShape(RoundedRectangle(cornerRadius: 14))
        }
    }

    /// Her iki modda da gösterilir — hem yeni üretilmiş hem kayıtlı bir
    /// itinerary Trip'e uygulanabilir (Req 10: yalnızca .viewSaved/generated
    /// sonuçlar için, yani her zaman burada — boş itinerary emptyState'e düşer).
    private var applyButton: some View {
        Button {
            showApplyConfirm = true
        } label: {
            ZStack {
                Text("Trip'e Uygula")
                    .opacity(vm.isApplying ? 0 : 1)
                ProgressView().tint(AppColors.onAccent)
                    .opacity(vm.isApplying ? 1 : 0)
            }
            .font(.system(size: 15, weight: .bold))
            .foregroundStyle(AppColors.onAccent)
            .frame(maxWidth: .infinity)
            .padding(.vertical, 14)
            .background(AppColors.accent)
            .clipShape(RoundedRectangle(cornerRadius: 14))
        }
        .disabled(vm.isApplying)
        // "Trip'e Uygula" metni ve gizli `ProgressView` AYNI ZStack'te
        // üst üste durduğundan (opacity ile geçiş, koşullu DEĞİŞTİRME
        // değil), açık bir etiket olmadan VoiceOver ikisini de anons
        // edebilirdi — diğer auth düğmeleriyle AYNI netlik (M36 audit
        // bulgusu).
        .accessibilityLabel(vm.isApplying ? "Uygulanıyor" : "Trip'e Uygula")
    }
}
