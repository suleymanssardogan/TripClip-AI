import SwiftUI

/// AI Trip Optimizer — bir Trip için üretilmiş itinerary'lerin geçmişi.
/// TripsListView ile aynı liste-ekranı deseni (yükleme/hata/boş/liste
/// dörtlüsü, PressableButtonStyle + NavigationLink satırları). Bir satıra
/// dokunmak, itinerary'i TripOptimizerView'da `.viewSaved` modunda açar —
/// optimizer TEKRAR ÇALIŞTIRILMAZ, yalnızca kayıtlı sonuç yüklenir.
struct ItineraryHistoryView: View {

    let tripID: Int
    /// TripOptimizerView'a taşınır — başarılı bir "Trip'e Uygula" sonrası
    /// TripDetailView'i yeniden yükler (bkz. TripDetailView).
    var onApplied: (() -> Void)? = nil
    /// Başarılı bir silme sonrası çağrılır — `onApplied` ile AYNI gerekçe:
    /// `TripDetailView`, geçmişteki bir itinerary silindiğinde kendi
    /// `hasItineraryHistory` toolbar ikonunu VE (silinen itinerary o an
    /// uygulanmış olansa) "uygulandı" banner'ını YENİDEN YÜKLEMELİ. Bu
    /// callback eklenmeden önce bu ekrandaki silme yalnızca KENDİ yerel
    /// listesini güncelliyordu, `TripDetailView`'a hiçbir sinyal
    /// göndermiyordu (M35 audit bulgusu).
    var onDeleted: (() -> Void)? = nil

    @Environment(AuthEnvironment.self) private var auth
    @State private var vm = ItineraryHistoryViewModel()
    /// Silme onayı bekleyen satır — `nil` iken hiçbir dialog gösterilmiyor.
    /// Doğrudan `Bool` yerine `ItinerarySummary?` tutuluyor: onay mesajının
    /// HANGİ itinerary'nin silineceğini açıkça belirtmesi gerekiyor (Req
    /// "The confirmation should clearly identify the itinerary being
    /// deleted") — `summary.formattedCreatedAt` bunun için yeterli/mevcut.
    @State private var itineraryPendingDeletion: ItinerarySummary?

    var body: some View {
        ZStack {
            AppColors.background.ignoresSafeArea()

            if vm.isLoading && vm.itineraries.isEmpty {
                ProgressView().tint(AppColors.accentText)
                    .accessibilityLabel("Yükleniyor")
            } else if let error = vm.error, vm.itineraries.isEmpty {
                errorState(error)
            } else if vm.itineraries.isEmpty {
                emptyState
            } else {
                list
            }
        }
        .navigationTitle("Optimizasyon Geçmişi")
        .navigationBarTitleDisplayMode(.inline)
        .task { await vm.load(tripID: tripID, auth: auth) }
        .refreshable { await vm.load(tripID: tripID, auth: auth) }
        // TripDetailView'ın kendi "Bu geziyi silmek istiyor musun?" silme
        // onayıyla AYNI desen (confirmationDialog + "Sil"/"Vazgeç", bkz. o
        // dosya) — ikinci bir onay biçimi İCAT EDİLMEDİ.
        .confirmationDialog(
            "Bu optimizasyon geçmişini silmek istediğine emin misin?",
            isPresented: Binding(
                get: { itineraryPendingDeletion != nil },
                set: { if !$0 { itineraryPendingDeletion = nil } }
            ),
            titleVisibility: .visible
        ) {
            Button("Sil", role: .destructive) {
                if let summary = itineraryPendingDeletion {
                    Task {
                        if await vm.deleteItinerary(id: summary.id, auth: auth) {
                            onDeleted?()
                        }
                    }
                }
                itineraryPendingDeletion = nil
            }
            Button("Vazgeç", role: .cancel) { itineraryPendingDeletion = nil }
        } message: {
            if let summary = itineraryPendingDeletion, !summary.formattedCreatedAt.isEmpty {
                Text("\(summary.formattedCreatedAt) tarihli bu itinerary kalıcı olarak silinecek. Bu işlem geri alınamaz.")
            } else {
                Text("Bu işlem geri alınamaz.")
            }
        }
        .alert(
            "Silinemedi",
            isPresented: Binding(
                get: { vm.deleteError != nil },
                set: { if !$0 { vm.deleteError = nil } }
            )
        ) {
            Button("Tamam", role: .cancel) { vm.deleteError = nil }
        } message: {
            Text(vm.deleteError ?? "")
        }
    }

    private var list: some View {
        ScrollView {
            LazyVStack(spacing: 10) {
                ForEach(vm.itineraries) { summary in
                    NavigationLink(destination: TripOptimizerView(mode: .viewSaved(itineraryID: summary.id), onApplied: onApplied)) {
                        ItineraryHistoryRowView(summary: summary)
                            // Silme sürerken satırı görsel olarak meşgul göster —
                            // yeni bir yükleme göstergesi İCAT EDİLMEDİ, mevcut
                            // "isApplying sırasında opacity düşür" deseniyle
                            // AYNI dil (bkz. TripOptimizerView.applyButton).
                            .opacity(vm.deletingID == summary.id ? 0.5 : 1)
                    }
                    .buttonStyle(PressableButtonStyle())
                    // TÜM satırlar (yalnızca silinen DEĞİL) devre dışı —
                    // `ItineraryApplyHistoryView`in `.disabled(vm.undoingID
                    // != nil)` deseniyle AYNI. `deletingID` zaten VM
                    // seviyesinde global bir re-entrancy koruması (bkz.
                    // deleteItinerary), ama önceden yalnızca dokunulan satır
                    // görsel olarak devre dışı bırakılıyordu — kullanıcı BİR
                    // satırı silerken BAŞKA bir satırı silmeye çalışırsa
                    // hiçbir geri bildirim olmadan sessizce hiçbir şey
                    // olmuyordu (M35 audit bulgusu).
                    .disabled(vm.deletingID != nil)
                    // HistoryView.swift'teki (Core Data geçmişi) AYNI
                    // ScrollView+LazyVStack içi `.swipeActions` deseni —
                    // `List`e geçmeye gerek yok, bu proje zaten bu tam
                    // kombinasyonda çalıştığını kanıtlamış durumda.
                    .swipeActions(edge: .trailing, allowsFullSwipe: true) {
                        Button(role: .destructive) {
                            itineraryPendingDeletion = summary
                        } label: {
                            Label("Sil", systemImage: "trash")
                        }
                    }
                }
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 12)
        }
    }

    private var emptyState: some View {
        VStack(spacing: 16) {
            Spacer()
            Image(systemName: "clock.arrow.circlepath")
                .font(.system(size: 52))
                .foregroundStyle(AppColors.textTertiary)
            Text("Henüz optimizasyon geçmişi yok")
                .font(.system(size: 18, weight: .semibold))
                .foregroundStyle(AppColors.text)
            Text("\"Optimize Et\" ile ilk itinerary'ini oluştur,\nburada saklanır.")
                .font(.system(size: 14))
                .foregroundStyle(AppColors.textSecondary)
                .multilineTextAlignment(.center)
            Spacer()
        }
        .padding(.horizontal, 32)
    }

    private func errorState(_ error: APIError) -> some View {
        VStack(spacing: 16) {
            Spacer()
            Image(systemName: "wifi.exclamationmark")
                .font(.system(size: 48))
                .foregroundStyle(AppColors.destructive)
            Text(error.localizedDescription ?? "Bir hata oluştu.")
                .font(.system(size: 15))
                .foregroundStyle(AppColors.textSecondary)
                .multilineTextAlignment(.center)
                .padding(.horizontal, 40)
            Button("Tekrar Dene") { Task { await vm.load(tripID: tripID, auth: auth) } }
                .foregroundStyle(AppColors.accentText)
            Spacer()
        }
    }
}
