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
        case generate(tripID: Int, placeIDs: [Int], durationDays: Int? = nil)
        case viewSaved(itineraryID: Int)
    }

    let mode: Mode
    /// Başarılı "Trip'e Uygula" sonrası çağrılır — çağıran taraf TripDetailView'i
    /// yeniden yükler (bkz. docs/ios-trip-optimizer.md "Apply to Trip").
    var onApplied: (() -> Void)? = nil

    @Environment(AuthEnvironment.self) private var auth
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
        case .generate(let tripID, let placeIDs, let durationDays):
            await vm.optimize(tripID: tripID, placeIDs: placeIDs, durationDays: durationDays, auth: auth)
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
        ScrollViewReader { proxy in
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                OptimizerRouteMapSection(
                    itinerary: itinerary,
                    selection: $selection,
                    onStopSelectedFromMap: { stop in
                        // Req 2 "Map → Itinerary": itinerary listesini,
                        // haritada dokunulan durağın satırına kaydır —
                        // TripDetailView'in kendi mapAnchor/scrollTo
                        // desenindeki AYNI mekanizma, ters yönde.
                        withAnimation {
                            proxy.scrollTo(ItineraryDaySection.rowID(for: stop.id), anchor: .center)
                        }
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
    }
}
