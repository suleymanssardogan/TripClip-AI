import SwiftUI

struct TripDetailView: View {

    let tripID:        Int
    var preloaded:     TripDetail? = nil

    @Environment(AuthEnvironment.self) private var auth
    /// Ekran ömrünü aşan, uygulama oturumu boyunca yaşayan, trip-bazlı
    /// paylaşılan optimizer yapılandırma önbelleği — `TripOptimizerConfigView`'a
    /// `init` parametresi olarak geçiriliyor (bkz. o dosyadaki doc yorumu —
    /// `@Environment`'ın orada doğrudan okunamama nedeni, `OptimizerRouteCache`
    /// ile AYNI desen). Bkz. docs/ios-trip-optimizer.md "Persistent
    /// Optimizer Configuration".
    @Environment(OptimizerConfigurationStore.self) private var optimizerConfigStore
    @Environment(\.dismiss) private var dismiss
    @State private var vm = TripDetailViewModel()
    /// Harita ↔ itinerary listesi arasında PAYLAŞILAN tek seçim — optimizer
    /// sonuç ekranıyla AYNI, zaten var olan tip (`OptimizerSelection`), yeni
    /// bir seçim durumu İCAT EDİLMEDİ (Req 3 "reuse existing... map/selection
    /// infrastructure").
    @State private var selection = OptimizerSelection()
    @State private var isEditing = false
    @State private var showDeleteConfirm = false
    /// Silme onayı bekleyen durak — trip-seviyesi silme (showDeleteConfirm)
    /// ile AYNI desen: geri alınamayan bir işlem tek dokunuşla DEĞİL, onaydan
    /// sonra gerçekleşmeli (M34 audit bulgusu).
    @State private var stopPendingDeletion: TripStop?
    /// Trip Assistant'ın sohbet durumu — burada, `TripDetailView` seviyesinde
    /// sahiplenilir (assistant ekranının KENDİ `@State`'i olarak DEĞİL), böylece
    /// referans durağa dokunup assistant'tan çıkıp geri dönmek sohbeti
    /// SIFIRLAMAZ (M35 audit bulgusu — bkz. TripAssistantView'daki doc yorumu).
    @State private var assistantVM = TripAssistantViewModel()

    private static let mapAnchor = "trip-detail-map"
    private static func stopRowID(_ placeId: Int) -> String { "trip-detail-stop-\(placeId)" }

    var body: some View {
        ZStack {
            AppColors.background.ignoresSafeArea()

            // Yalnızca İLK yüklemede tam ekran spinner/hata göster — bu ekran,
            // zaten görüntülenen bir trip'i (harita+durak listesi) apply/undo/
            // itinerary-silme gibi HER arka plan yeniden yüklemesinde tamamen
            // söküp yeniden kuruyordu (M37 audit bulgusu: "Trip'e Uygula" →
            // onay → başarı sonrası kullanıcı bir an tam ekran spinner görüp
            // içerik yeniden çiziliyordu). `TripsListView`/`LibraryView`/
            // `HomeView`'in KENDİ AYNI "isLoading && collection.isEmpty" deseni
            // — burada `vm.trip == nil` karşılığı.
            if vm.isLoading, vm.trip == nil {
                ProgressView().tint(AppColors.accentText)
                    .accessibilityLabel("Yükleniyor")
            } else if let error = vm.error, vm.trip == nil {
                errorView(error)
            } else if let trip = vm.trip {
                tripContent(trip)
            }
        }
        .navigationTitle(vm.trip?.title ?? "Gezi")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            if let trip = vm.trip, !trip.allStops.isEmpty {
                ToolbarItem(placement: .navigationBarTrailing) {
                    NavigationLink(
                        destination: TripAssistantView(
                            tripID: trip.id, trip: trip, vm: assistantVM,
                            onFocusStop: { dayIndex, placeId in
                                // Asistanın referans çipindeki `dayIndex` BAYAT
                                // olabilir — sohbet açıkken (assistantVM kalıcı
                                // olduğundan sohbet uzun yaşayabilir) bir apply/
                                // undo trip'in gün yapısını değiştirmiş olabilir.
                                // Ham `dayIndex`e KÖRÜ KÖRÜNE güvenmek yerine,
                                // durağı GÜNCEL `trip`te KENDİ gerçek `dayIndex`iyle
                                // yeniden buluyoruz — `selectStop`'un AYNI ilkesi
                                // (bkz. az aşağısı). Bulunamazsa (durak silinmiş)
                                // yalnızca stopID taşınır ve `dayIndex` `nil`e
                                // düşer ("Tümü") — ASLA artık var olmayan bir
                                // güne göre filtrelenip durak listesini görünürde
                                // BOŞALTMAZ (M37 audit bulgusu).
                                let currentStop = trip.allStops.first { $0.placeId == placeId }
                                selection = OptimizerSelection(dayIndex: currentStop?.dayIndex, stopID: String(placeId))
                            }
                        )
                    ) {
                        Image(systemName: "message")
                            .foregroundStyle(AppColors.accentText)
                    }
                    .accessibilityLabel("AI Asistan")
                }
            }
            if let trip = vm.trip, !trip.allStops.isEmpty {
                ToolbarItem(placement: .navigationBarTrailing) {
                    NavigationLink(
                        destination: TripOptimizerConfigView(
                            tripID: trip.id,
                            stops: trip.allStops,
                            configStore: optimizerConfigStore,
                            onApplied: { Task { await vm.load(tripID: tripID, auth: auth) } }
                        )
                    ) {
                        Image(systemName: "sparkles")
                            .foregroundStyle(AppColors.accentText)
                    }
                    .accessibilityLabel("Geziyi Optimize Et")
                }
            }
            if let trip = vm.trip, vm.hasItineraryHistory {
                ToolbarItem(placement: .navigationBarTrailing) {
                    NavigationLink(
                        destination: ItineraryHistoryView(
                            tripID: trip.id,
                            onApplied: { Task { await vm.load(tripID: tripID, auth: auth) } },
                            // Silinen itinerary o an UYGULANMIŞ olabilir (trip'in
                            // appliedItineraryId'si buna işaret ediyor olabilir —
                            // core-api silme sırasında bunu sunucu tarafında
                            // temizler) veya geçmişteki SON itinerary olabilir
                            // (toolbar ikonu artık gizlenmeli) — her iki durumda
                            // da hem trip'i hem de geçmiş bayrağını YENİDEN
                            // yüklemek gerekir (M35 audit bulgusu: bu callback
                            // eklenmeden önce hiçbiri tetiklenmiyordu).
                            onDeleted: {
                                Task {
                                    await vm.load(tripID: tripID, auth: auth)
                                    await vm.refreshItineraryHistoryFlag(tripID: tripID, auth: auth)
                                }
                            }
                        )
                    ) {
                        Image(systemName: "clock.arrow.circlepath")
                            .foregroundStyle(AppColors.accentText)
                    }
                    .accessibilityLabel("Optimizasyon Geçmişi")
                }
            }
            if let trip = vm.trip, vm.hasApplyHistory {
                ToolbarItem(placement: .navigationBarTrailing) {
                    NavigationLink(
                        destination: ItineraryApplyHistoryView(
                            tripID: trip.id,
                            onChanged: { Task { await vm.load(tripID: tripID, auth: auth) } }
                        )
                    ) {
                        Image(systemName: "arrow.uturn.backward.circle")
                            .foregroundStyle(AppColors.accentText)
                    }
                    .accessibilityLabel("Uygulama Geçmişi")
                }
            }
            if vm.trip != nil {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button(role: .destructive) {
                        showDeleteConfirm = true
                    } label: {
                        if vm.isDeleting {
                            ProgressView().tint(AppColors.destructive)
                        } else {
                            Image(systemName: "trash")
                                .foregroundStyle(AppColors.destructive)
                        }
                    }
                    .disabled(vm.isDeleting)
                    .accessibilityLabel("Geziyi sil")
                }
            }
        }
        .confirmationDialog(
            "Bu geziyi silmek istiyor musun?",
            isPresented: $showDeleteConfirm,
            titleVisibility: .visible
        ) {
            Button("Sil", role: .destructive) {
                Task {
                    if await vm.deleteTrip(auth: auth) { dismiss() }
                }
            }
            Button("Vazgeç", role: .cancel) { }
        } message: {
            Text("Bu işlem geri alınamaz.")
        }
        .confirmationDialog(
            "Bu durağı silmek istiyor musun?",
            isPresented: Binding(
                get: { stopPendingDeletion != nil },
                set: { if !$0 { stopPendingDeletion = nil } }
            ),
            titleVisibility: .visible
        ) {
            Button("Sil", role: .destructive) {
                guard let stop = stopPendingDeletion else { return }
                stopPendingDeletion = nil
                if selection.stopID == String(stop.placeId) { selection = OptimizerSelection() }
                Task { await vm.deleteStop(stop, auth: auth) }
            }
            Button("Vazgeç", role: .cancel) { stopPendingDeletion = nil }
        } message: {
            Text("Bu işlem geri alınamaz.")
        }
        .alert(
            "Değişiklik kaydedilemedi",
            isPresented: Binding(
                get: { vm.stopEditError != nil },
                set: { if !$0 { vm.stopEditError = nil } }
            )
        ) {
            Button("Tamam", role: .cancel) { vm.stopEditError = nil }
        } message: {
            Text(vm.stopEditError ?? "")
        }
        // `vm.deleteError` daha önce hiçbir yere BAĞLANMAMIŞTI — bir gezi
        // silme isteği başarısız olduğunda (ağ hatası, sunucu hatası) HİÇBİR
        // geri bildirim yoktu: ne bir alert, ne de çöp kutusu düğmesi devre
        // dışı kalıyordu. `stopEditError`in az yukarıdaki AYNI alert
        // deseniyle, ve `ItineraryHistoryView`/`ItineraryApplyHistoryView`'in
        // kendi silme/undo hata alert'leriyle TUTARLI (M36 audit bulgusu).
        .alert(
            "Gezi silinemedi",
            isPresented: Binding(
                get: { vm.deleteError != nil },
                set: { if !$0 { vm.deleteError = nil } }
            )
        ) {
            Button("Tamam", role: .cancel) { vm.deleteError = nil }
        } message: {
            Text(vm.deleteError ?? "")
        }
        .task { await vm.load(tripID: tripID, auth: auth, preloaded: preloaded) }
        .task { await vm.refreshItineraryHistoryFlag(tripID: tripID, auth: auth) }
        .task { await vm.refreshApplyHistoryFlag(tripID: tripID, auth: auth) }
        // `TripsListView`/`LibraryView`/`HomeView`'in AYNI `.refreshable`
        // deseni — bu ekran daha önce hiç manuel yenileme jesti sunmuyordu,
        // oysa optimizer/apply-history/itinerary-geçmişi mutasyonlarının
        // hepsinin dokunduğu, muhtemelen en çok bayatlayabilecek ekran
        // (M37 audit bulgusu).
        .refreshable {
            await vm.load(tripID: tripID, auth: auth)
            await vm.refreshItineraryHistoryFlag(tripID: tripID, auth: auth)
            await vm.refreshApplyHistoryFlag(tripID: tripID, auth: auth)
        }
        // M36 audit bulgusu (VERİ KAYBI riski): `isEditing` yalnızca "Düzenle"
        // düğmesiyle açılıyordu ve BAŞKA HİÇBİR YERDE kapatılmıyordu. Kullanıcı
        // tek günlü bir trip'te düzenleme modunu AÇIP (o an `canEditStops` true'ydu)
        // ekrandan ayrılmadan (Optimizer/Apply History gibi araç çubuğu
        // bağlantıları düzenleme sırasında da erişilebilir kalıyor) çok günlü bir
        // duruma geçen bir apply/undo tetiklerse, `hasMultipleDays` true olur ve
        // "Düzenle/Bitti" düğmesi GİZLENİR (kullanıcı artık kapatamaz) — ama
        // `isEditing` hâlâ true kalır, bu yüzden TÜM günlerin durakları hâlâ
        // sil/taşı kontrolleriyle render edilir. `TripDetailViewModel.persistDay`
        // yalnızca `trip.days.first`i okuyup YAZAR (`current.days = [day]`) —
        // başka bir güne ait bir durağı silmek/taşımak o günü YEREL olarak
        // sessizce değiştirmez ama `persistDay` trip'in TÜM `days`'ini TEK güne
        // indirger ve sunucuya YALNIZCA o tek günü gönderir, diğer günleri hem
        // yerel state'te hem sunucuda SİLER. Trip'in gün yapısı değiştiğinde
        // (apply/undo sonrası) düzenleme modunu ZORLA kapatarak bu senaryo
        // yapısal olarak imkansız hale getiriliyor.
        //
        // Aynı yerde, `selection.dayIndex` de artık var olmayan bir güne işaret
        // edebilir (ör. 2. Gün seçiliyken bir undo trip'i tek güne indirger) —
        // `visibleDays` bu durumda BOŞ bir dizi üretip durak listesini görünürde
        // KAYBOLDURUR ("Duraklar (N)" başlığı hâlâ doğru sayıyı gösterirken).
        // `dayIndex`i yalnızca artık geçersizse "Tümü"ne (nil) düşürmek bunu
        // kendiliğinden düzeltir.
        .onChange(of: vm.trip?.days.count) { _, _ in
            guard let trip = vm.trip else { return }
            if trip.days.count > 1 {
                isEditing = false
            }
            if let dayIndex = selection.dayIndex, !trip.days.contains(where: { $0.first?.dayIndex == dayIndex }) {
                selection = OptimizerSelection(dayIndex: nil, stopID: selection.stopID)
            }
        }
    }

    @ViewBuilder
    private func tripContent(_ trip: TripDetail) -> some View {
        let stops: [TripStop] = trip.allStops
        let pins: [LocationPin] = stops.map(\.asLocationPin)
        // `TripMapView`'ın kendi otoriter bir odak state'i yok — paylaşılan
        // `selection`'ın salt-okunur bir izdüşümü (bkz. `ItineraryDaySection`'ın
        // AYNI ilkesi, "kendi otoriter seçim state'ini icat etmez").
        let focusedPin: LocationPin? = selection.stopID.flatMap { id in
            stops.first(where: { String($0.placeId) == id })?.asLocationPin
        }
        // Çok günlü bir trip'te (Apply sonrası mümkün — bkz. TripStop.dayIndex)
        // TÜM durakları TEK bir düz çizgiyle bağlamak günler arasında yanıltıcı
        // bir rota çizerdi (Req 4 "no cross-day polyline"). `TripMapView`'ın
        // kendisi gün-farkında değil (Results ekranıyla PAYLAŞILAN, tek renkli/
        // tek rotalı basit bir bileşen) — yeni bir çok-renkli rota mimarisi
        // İCAT ETMEK yerine, çok günlü durumda rota çizgisini basitçe
        // GÖSTERMİYORUZ (pinler yine de görünür kalır); tek günlü trip'ler
        // (bugün hâlâ yaygın durum) hiçbir davranış değişikliği görmez.
        let route: [RoutePoint]? = trip.days.count > 1 ? nil : mapRoute(for: stops)
        let hasMultipleDays = trip.days.count > 1
        // Düzenleme (sıralama/silme) yalnızca TEK güne yazıyor
        // (`TripDetailViewModel.persistDay` → `trip.days.first`) — çok günlü
        // bir trip'te "Düzenle"yi göstermek, kullanıcı 2. Gün'ü görüntülerken
        // sessizce 1. Gün'ü düzenlemesine yol açardı. Gün navigasyonunun kendisi
        // bu riski YENİ ortaya çıkardığı için (öncesinde çok günlü bir görünüm
        // hiç yoktu), en küçük hedefli düzeltme: çok günlü trip'lerde "Düzenle"
        // affordance'ını tamamen gizle.
        let canEditStops = !hasMultipleDays

        ScrollViewReader { proxy in
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {

                if !stops.isEmpty {
                    TripMapView(
                        locations: pins, route: route, focusedPin: focusedPin,
                        onSelectPin: { pin in
                            guard let stop = stops.first(where: { $0.placeId == pin.index }) else { return }
                            selectStop(stop)
                            withAnimation { proxy.scrollTo(Self.stopRowID(stop.placeId), anchor: .center) }
                        }
                    )
                    .frame(height: 260)
                    .clipShape(RoundedRectangle(cornerRadius: 20))
                    .padding(.horizontal, 16)
                    .id(Self.mapAnchor)
                }

                statsStrip(trip).padding(.horizontal, 16)

                if trip.appliedItineraryId != nil {
                    appliedItineraryBanner(trip).padding(.horizontal, 16)
                }

                if !stops.isEmpty {
                    stopsHeader(stops.count, canEdit: canEditStops)

                    if hasMultipleDays && !isEditing {
                        daySelector(trip).padding(.horizontal, 16)
                    }

                    let visibleDays: [[TripStop]] = selection.dayIndex == nil
                        ? trip.days
                        : trip.days.filter { $0.first?.dayIndex == selection.dayIndex }

                    VStack(alignment: .leading, spacing: 16) {
                        ForEach(Array(visibleDays.enumerated()), id: \.offset) { _, dayStops in
                            if hasMultipleDays && selection.dayIndex == nil, let dayIndex = dayStops.first?.dayIndex {
                                Text("\(dayIndex + 1). Gün")
                                    .font(.system(size: 13, weight: .semibold))
                                    .foregroundStyle(AppColors.textSecondary)
                                    .textCase(.uppercase)
                                    .tracking(0.8)
                            }
                            VStack(spacing: 8) {
                                ForEach(dayStops, id: \.placeId) { stop in
                                    if isEditing, let offset = stops.firstIndex(where: { $0.placeId == stop.placeId }) {
                                        LocationCard(
                                            number: stop.orderIndex + 1,
                                            pin:    stop.asLocationPin,
                                            edit:   editActions(for: offset, stop: stop, count: stops.count)
                                        )
                                    } else {
                                        Button {
                                            selectStop(stop)
                                            withAnimation { proxy.scrollTo(Self.mapAnchor, anchor: .top) }
                                        } label: {
                                            LocationCard(
                                                number: stop.orderIndex + 1, pin: stop.asLocationPin,
                                                isSelected: selection.stopID == String(stop.placeId)
                                            )
                                        }
                                        .buttonStyle(PressableButtonStyle())
                                        .id(Self.stopRowID(stop.placeId))
                                    }
                                }
                            }
                        }
                    }
                    .padding(.horizontal, 16)
                    .disabled(vm.isSavingStops)
                } else {
                    emptyStopsState.padding(.horizontal, 16)
                }

                Color.clear.frame(height: 40)
            }
            .padding(.top, 16)
        }
        }
    }

    private func stopsHeader(_ count: Int, canEdit: Bool) -> some View {
        HStack {
            Text("Duraklar (\(count))")
                .font(.system(size: 14, weight: .semibold))
                .foregroundStyle(AppColors.textSecondary)
                .textCase(.uppercase)
                .tracking(0.8)

            Spacer()

            if vm.isSavingStops {
                ProgressView().controlSize(.small).tint(AppColors.accentText)
            } else if canEdit {
                Button(isEditing ? "Bitti" : "Düzenle") {
                    withAnimation { isEditing.toggle() }
                }
                .font(.system(size: 14, weight: .semibold))
                .foregroundStyle(AppColors.accentText)
            }
        }
        .padding(.horizontal, 16)
    }

    private func editActions(for offset: Int, stop: TripStop, count: Int) -> LocationCard.EditActions {
        LocationCard.EditActions(
            canMoveUp:   offset > 0,
            canMoveDown: offset < count - 1,
            onMoveUp: {
                Task { await vm.moveStops(from: [offset], to: offset - 1, auth: auth) }
            },
            onMoveDown: {
                Task { await vm.moveStops(from: [offset], to: offset + 2, auth: auth) }
            },
            onDelete: {
                stopPendingDeletion = stop
            }
        )
    }

    // MARK: - Seçim (Req 1/2/3 "map ↔ itinerary experience")

    /// Bir durağa (haritadan ya da itinerary listesinden) dokunulduğunda —
    /// `OptimizerSelection.focusing` ile AYNI, zaten test edilmiş kural:
    /// durak zaten aktif günün içindeyse gün değişmez, değilse o güne geçilir.
    private func selectStop(_ stop: TripStop) {
        selection = .focusing(dayIndex: stop.dayIndex, stopID: String(stop.placeId))
    }

    /// Gün çipine doğrudan dokunmak — seçili durak yeni günün kapsamında
    /// değilse TEMİZLENİR, kapsamdaysa (ör. "Tümü"den o durağın kendi
    /// gününe geçmek) KORUNUR. Web'in `selectDay()`'iyle AYNI kural (bkz.
    /// docs/web-trip-optimizer.md "Map camera: selection-driven").
    private func selectDay(_ dayIndex: Int?, in trip: TripDetail) {
        let scope: [TripStop] = dayIndex == nil ? trip.allStops : (trip.days.first { $0.first?.dayIndex == dayIndex } ?? [])
        let stopStillInScope = selection.stopID.map { id in scope.contains { String($0.placeId) == id } } ?? false
        selection = OptimizerSelection(dayIndex: dayIndex, stopID: stopStillInScope ? selection.stopID : nil)
    }

    private func daySelector(_ trip: TripDetail) -> some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 8) {
                dayChip(title: "Tümü", isSelected: selection.dayIndex == nil) {
                    selectDay(nil, in: trip)
                }
                ForEach(trip.days.compactMap(\.first?.dayIndex), id: \.self) { dayIndex in
                    dayChip(title: "\(dayIndex + 1). Gün", isSelected: selection.dayIndex == dayIndex) {
                        selectDay(dayIndex, in: trip)
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
        .accessibilityAddTraits(isSelected ? [.isSelected] : [])
    }

    // MARK: - Uygulanan itinerary göstergesi (Req 8 "apply-state awareness")

    /// Backend bu alanları zaten gönderiyordu (`TripDetail.appliedItineraryId`),
    /// yalnızca hiç YÜZEYE ÇIKARILMIYORDU — yeni bir API/mutasyon YOK, salt
    /// mevcut state'in sunumu. "Uygulama Geçmişi"ne, toolbar'daki AYNI
    /// hedefe (`ItineraryApplyHistoryView`) götürür — yeni bir ekran İCAT
    /// EDİLMEDİ.
    private func appliedItineraryBanner(_ trip: TripDetail) -> some View {
        NavigationLink(destination: ItineraryApplyHistoryView(
            tripID: trip.id, onChanged: { Task { await vm.load(tripID: tripID, auth: auth) } }
        )) {
            HStack(spacing: 10) {
                Image(systemName: "checkmark.seal.fill")
                    .font(.system(size: 16))
                    .foregroundStyle(AppColors.route)
                VStack(alignment: .leading, spacing: 1) {
                    Text("Bir optimizer itinerary'si uygulandı")
                        .font(.system(size: 13, weight: .semibold))
                        .foregroundStyle(AppColors.text)
                    if !trip.formattedItineraryAppliedAt.isEmpty {
                        Text(trip.formattedItineraryAppliedAt)
                            .font(.system(size: 12))
                            .foregroundStyle(AppColors.textSecondary)
                    }
                }
                Spacer()
                Image(systemName: "chevron.right")
                    .font(.system(size: 12, weight: .semibold))
                    .foregroundStyle(AppColors.textTertiary)
            }
            .padding(12)
            .background(AppColors.route.opacity(0.08))
            .clipShape(RoundedRectangle(cornerRadius: 14))
            .overlay(RoundedRectangle(cornerRadius: 14).stroke(AppColors.route.opacity(0.2), lineWidth: 1))
        }
        .buttonStyle(PressableButtonStyle())
    }

    private var emptyStopsState: some View {
        VStack(spacing: 10) {
            Image(systemName: "mappin.slash")
                .font(.system(size: 32))
                .foregroundStyle(AppColors.textTertiary)
            Text("Tüm duraklar silindi")
                .font(.system(size: 14))
                .foregroundStyle(AppColors.textSecondary)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 24)
    }

    private func statsStrip(_ trip: TripDetail) -> some View {
        HStack(spacing: 0) {
            statCell(icon: "mappin.circle.fill", value: "\(trip.allStops.count)", label: "Durak")
            Divider().frame(height: 36).background(AppColors.border)
            statCell(icon: "arrow.triangle.swap", value: distanceString(trip.totalDistanceKm), label: "Mesafe")
            Divider().frame(height: 36).background(AppColors.border)
            statCell(icon: "calendar", value: trip.formattedCreatedAt.isEmpty ? "—" : trip.formattedCreatedAt, label: "Oluşturuldu")
        }
        .padding(.vertical, 14)
        .background(AppColors.surface)
        .clipShape(RoundedRectangle(cornerRadius: 16))
        .overlay(RoundedRectangle(cornerRadius: 16).stroke(AppColors.border, lineWidth: 1))
    }

    private func statCell(icon: String, value: String, label: String) -> some View {
        VStack(spacing: 4) {
            Image(systemName: icon).foregroundStyle(AppColors.textTertiary).font(.system(size: 16))
            Text(value).font(.system(size: 13, weight: .bold)).foregroundStyle(AppColors.text).lineLimit(1)
            Text(label).font(.system(size: 11)).foregroundStyle(AppColors.textSecondary)
        }
        .frame(maxWidth: .infinity)
    }

    private func mapRoute(for stops: [TripStop]) -> [RoutePoint]? {
        guard stops.count > 1 else { return nil }
        return stops.map { RoutePoint(latitude: $0.latitude, longitude: $0.longitude, name: $0.name) }
    }

    private func distanceString(_ km: Double?) -> String {
        guard let km, km > 0 else { return "—" }
        return String(format: "%.1f km", km)
    }

    private func errorView(_ error: APIError) -> some View {
        VStack(spacing: 16) {
            Image(systemName: "exclamationmark.triangle")
                .font(.system(size: 48))
                .foregroundStyle(AppColors.destructive)
            Text(error.localizedDescription ?? "Yüklenemedi.")
                .foregroundStyle(AppColors.textSecondary)
                .multilineTextAlignment(.center)
                .padding(.horizontal, 40)
            Button("Tekrar Dene") {
                Task { await vm.load(tripID: tripID, auth: auth) }
            }
            .foregroundStyle(AppColors.accentText)
        }
    }
}
