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

    init(
        tripID: Int, stops: [TripStop], configStore: OptimizerConfigurationStore,
        onApplied: (() -> Void)? = nil
    ) {
        self.tripID = tripID
        self.onApplied = onApplied
        _vm = State(initialValue: TripOptimizerConfigViewModel(
            tripID: tripID, stops: stops, configStore: configStore
        ))
    }

    var body: some View {
        ZStack(alignment: .bottom) {
            AppColors.background.ignoresSafeArea()

            ScrollView {
                VStack(alignment: .leading, spacing: 24) {
                    placesSection
                    durationSection
                    preferredDateSection
                    preferredTimeSection
                    transportModeSection
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

    // MARK: - Preferred start date

    /// Opsiyonel planlama tarihi — core-api'nin zaten var olan `start_date`
    /// alanı (bkz. docs/ios-trip-optimizer.md "Trip Planning Date"). Kapalı
    /// (varsayılan): backend günleri yalnızca sıra numarasıyla döner ("1.
    /// Gün"). Açık: kullanıcının seçtiği tarihten başlayarak her gün gerçek
    /// bir takvim gününe karşılık gelir — hesaplama backend'de yapılır,
    /// burada HİÇBİR takvim aritmetiği yok.
    private var preferredDateSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Planlama Tarihi")
                .font(.system(size: 14, weight: .semibold))
                .foregroundStyle(AppColors.textSecondary)
                .textCase(.uppercase)
                .tracking(0.8)
                .padding(.horizontal, 16)

            VStack(spacing: 0) {
                Toggle(isOn: isDateEnabledBinding) {
                    Text(vm.preferredStartDate == nil ? "Tarih belirtilmedi" : "Belirli bir tarih")
                        .font(.system(size: 14, weight: .medium))
                        .foregroundStyle(AppColors.text)
                }
                .tint(AppColors.accent)
                .padding(.horizontal, 16)
                .padding(.vertical, 12)

                if vm.preferredStartDate != nil {
                    Divider().background(AppColors.border).padding(.horizontal, 16)
                    DatePicker(
                        "Tarih", selection: selectedDateBinding, displayedComponents: .date
                    )
                    .tint(AppColors.accent)
                    .padding(.horizontal, 16)
                    .padding(.vertical, 12)
                    .environment(\.locale, Locale(identifier: "tr_TR"))
                }
            }
            .background(AppColors.surface)
            .clipShape(RoundedRectangle(cornerRadius: 16))
            .overlay(RoundedRectangle(cornerRadius: 16).stroke(AppColors.border, lineWidth: 1))
            .padding(.horizontal, 16)

            Text(
                vm.preferredStartDate == nil
                    ? "Belirtilmezse günler yalnızca sıra numarasıyla gösterilir (1. Gün, 2. Gün, …)."
                    : "Günler bu tarihten itibaren gerçek takvim günleri olarak gösterilir."
            )
            .font(.system(size: 12))
            .foregroundStyle(AppColors.textSecondary)
            .padding(.horizontal, 16)
        }
    }

    /// Kapatmak seçimi `nil`e döndürür ("Otomatik"); açmak bugünün
    /// tarihiyle başlar (makul bir başlangıç noktası — kullanıcı istediği
    /// gibi değiştirebilir).
    private var isDateEnabledBinding: Binding<Bool> {
        Binding(
            get: { vm.preferredStartDate != nil },
            set: { enabled in
                vm.setPreferredStartDate(enabled ? PlanningDate(date: Date()) : nil)
            }
        )
    }

    private var selectedDateBinding: Binding<Date> {
        Binding(
            get: { vm.preferredStartDate?.asDate ?? Date() },
            set: { vm.setPreferredStartDate(PlanningDate(date: $0)) }
        )
    }

    // MARK: - Preferred start/end time

    /// Optimizerin günlük planlama penceresi — mekanların kendi açılış
    /// saatleri AYRI bir kısıttır, bu ekran onları göstermez/düzenlemez
    /// (bkz. `TripOptimizerConfigViewModel.preferredStartTime`,
    /// docs/trip-optimizer.md "Opening hours"). `.hourAndMinute` dışında
    /// bir bileşen yok — tarih/saat dilimi bu milestone'un kapsamı dışında
    /// (Req 16).
    private var preferredTimeSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Planlama Saatleri")
                .font(.system(size: 14, weight: .semibold))
                .foregroundStyle(AppColors.textSecondary)
                .textCase(.uppercase)
                .tracking(0.8)
                .padding(.horizontal, 16)

            VStack(spacing: 0) {
                timeRow(
                    title: "Başlangıç Saati",
                    time: Binding(
                        get: { vm.preferredStartTime.asDate },
                        set: { vm.setPreferredStartTime(ClockTime(date: $0)) }
                    )
                )
                Divider().background(AppColors.border).padding(.horizontal, 16)
                timeRow(
                    title: "Bitiş Saati",
                    time: Binding(
                        get: { vm.preferredEndTime.asDate },
                        set: { vm.setPreferredEndTime(ClockTime(date: $0)) }
                    )
                )
            }
            .background(AppColors.surface)
            .clipShape(RoundedRectangle(cornerRadius: 16))
            .overlay(RoundedRectangle(cornerRadius: 16).stroke(AppColors.border, lineWidth: 1))
            .padding(.horizontal, 16)
            // Cihazın bölge ayarı ne olursa olsun 24 saatlik "09:00" biçimi —
            // APIDate'in kendi tr_TR zorlama emsaliyle tutarlı.
            .environment(\.locale, Locale(identifier: "tr_TR"))

            if vm.isTimeRangeValid {
                Text("Optimizer günlük planı bu saat aralığına sığdırır. Mekanların kendi açılış saatleri ayrıca dikkate alınır.")
                    .font(.system(size: 12))
                    .foregroundStyle(AppColors.textSecondary)
                    .padding(.horizontal, 16)
            } else {
                Text("Başlangıç saati, bitiş saatinden önce olmalı.")
                    .font(.system(size: 12, weight: .semibold))
                    .foregroundStyle(AppColors.destructive)
                    .padding(.horizontal, 16)
            }
        }
    }

    // MARK: - Transport mode

    /// Haritanın (`OptimizerRouteMapSection`) rota gösterim tercihiyle
    /// PAYLAŞILAN tek ayar — ikinci bir state modeli YOK: `vm.transportMode`
    /// (`TripOptimizerConfigViewModel`) zaten `OptimizerConfigurationStore`'a
    /// yazıyor/okuyor, harita da AYNI kaydı kullanıyor (bkz.
    /// docs/ios-trip-optimizer.md "Persistent Optimizer Transport Mode
    /// Sync"). Bu bölüm yalnızca bu değeri değiştirmek için bir UI ekliyor
    /// — kalıcılık/senkronizasyon mantığından hiçbiri burada YOK.
    private var transportModeSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Ulaşım Modu")
                .font(.system(size: 14, weight: .semibold))
                .foregroundStyle(AppColors.textSecondary)
                .textCase(.uppercase)
                .tracking(0.8)
                .padding(.horizontal, 16)

            Picker("Ulaşım Modu", selection: transportModeBinding) {
                ForEach(OptimizerTransportMode.allCases, id: \.self) { mode in
                    Label(mode.title, systemImage: mode.symbolName)
                        .tag(mode)
                        .accessibilityLabel(mode.accessibilityLabel)
                }
            }
            .pickerStyle(.segmented)
            .padding(.horizontal, 16)
            .padding(.vertical, 12)
            .background(AppColors.surface)
            .clipShape(RoundedRectangle(cornerRadius: 16))
            .overlay(RoundedRectangle(cornerRadius: 16).stroke(AppColors.border, lineWidth: 1))
            .padding(.horizontal, 16)

            Text("Rota haritası bu tercihe göre hesaplanır. Mekanların optimize edilmiş sırasını etkilemez.")
                .font(.system(size: 12))
                .foregroundStyle(AppColors.textSecondary)
                .padding(.horizontal, 16)
        }
    }

    private var transportModeBinding: Binding<OptimizerTransportMode> {
        Binding(
            get: { vm.transportMode },
            set: { vm.setTransportMode($0) }
        )
    }

    private func timeRow(title: String, time: Binding<Date>) -> some View {
        DatePicker(selection: time, displayedComponents: .hourAndMinute) {
            Text(title)
                .font(.system(size: 14, weight: .medium))
                .foregroundStyle(AppColors.text)
        }
        .tint(AppColors.accent)
        .padding(.horizontal, 16)
        .padding(.vertical, 12)
    }

    // MARK: - Optimize CTA

    private var optimizeBar: some View {
        HStack {
            Text(optimizeBarMessage)
                .font(.system(size: 14, weight: .semibold))
                .foregroundStyle(vm.canOptimize ? AppColors.text : AppColors.destructive)

            Spacer()

            NavigationLink(
                destination: TripOptimizerView(
                    mode: .generate(
                        tripID: tripID,
                        placeIDs: vm.selectedPlaceIDsInTripOrder,
                        durationDays: vm.durationDays,
                        preferredStartTime: vm.preferredStartTime,
                        preferredEndTime: vm.preferredEndTime,
                        startDate: vm.preferredStartDate
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

    /// İki bağımsız geçersizlik nedeni olabildiğinden (Req 4: sıfır mekan
    /// YA DA geçersiz zaman aralığı), tek bir jenerik "geçersiz" metni
    /// yerine hangisinin geçerli olduğunu doğrudan söylüyoruz — kullanıcı
    /// neyi düzeltmesi gerektiğini tahmin etmek zorunda kalmaz.
    private var optimizeBarMessage: String {
        if vm.selectedCount == 0 { return "En az bir mekan seçmelisin" }
        if !vm.isTimeRangeValid { return "Başlangıç saati bitiş saatinden önce olmalı" }
        return "\(vm.selectedCount) mekan seçildi"
    }
}
