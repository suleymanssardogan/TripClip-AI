import SwiftUI

/// AI Trip Optimizer — bir Trip'e uygulanan (ve geri alınan) her değişikliğin
/// kalıcı geçmişi, en yeniden eskiye. `ItineraryHistoryView` ile AYNI liste-
/// ekranı deseni (yükleme/hata/boş/liste dörtlüsü) — bkz.
/// docs/ios-trip-optimizer.md "Apply History & Undo". Yalnızca EN SON kayıt
/// "Geri Al" gösterir (`entry.isUndoable`) — sunucunun kendi "latest-only"
/// güvenlik kuralının doğrudan yansıması, istemci bunu KENDİSİ türetmez.
struct ItineraryApplyHistoryView: View {

    let tripID: Int
    /// Başarılı bir "Geri Al" sonrası çağrılır — TripDetailView'i yeniden
    /// yükler (bkz. `ItineraryHistoryView.onApplied`/`TripOptimizerView.onApplied`
    /// ile AYNI callback-bubbling deseni).
    var onChanged: (() -> Void)? = nil

    @Environment(AuthEnvironment.self) private var auth
    @State private var vm = ItineraryApplyHistoryViewModel()
    @State private var entryPendingUndo: ApplyHistoryEntry?

    var body: some View {
        ZStack {
            AppColors.background.ignoresSafeArea()

            if vm.isLoading && vm.entries.isEmpty {
                ProgressView().tint(AppColors.accentText)
                    .accessibilityLabel("Yükleniyor")
            } else if let error = vm.error, vm.entries.isEmpty {
                errorState(error)
            } else if vm.entries.isEmpty {
                emptyState
            } else {
                list
            }
        }
        .navigationTitle("Uygulama Geçmişi")
        .navigationBarTitleDisplayMode(.inline)
        .task { await vm.load(tripID: tripID, auth: auth) }
        .refreshable { await vm.load(tripID: tripID, auth: auth) }
        .confirmationDialog(
            "Son optimizasyon uygulamasını geri almak istediğine emin misin?",
            isPresented: Binding(
                get: { entryPendingUndo != nil },
                set: { if !$0 { entryPendingUndo = nil } }
            ),
            titleVisibility: .visible
        ) {
            Button("Geri Al", role: .destructive) {
                if let entry = entryPendingUndo {
                    Task {
                        let success = await vm.undo(historyID: entry.id, tripID: tripID, auth: auth)
                        if success {
                            // Sunucu tek otorite — durumu YEREL olarak
                            // tahmin etmek yerine listeyi yeniden yükle
                            // (bkz. ItineraryApplyHistoryViewModel.undo
                            // doc yorumu), sonra TripDetailView'i de bilgilendir.
                            await vm.load(tripID: tripID, auth: auth)
                            onChanged?()
                        }
                    }
                }
                entryPendingUndo = nil
            }
            Button("Vazgeç", role: .cancel) { entryPendingUndo = nil }
        } message: {
            Text("Gezinin durak listesi bu geri almadan önceki hâline döner.")
        }
        .alert(
            "Geri Alınamadı",
            isPresented: Binding(
                get: { vm.undoError != nil },
                set: { if !$0 { vm.undoError = nil } }
            )
        ) {
            Button("Tamam", role: .cancel) { vm.undoError = nil }
        } message: {
            Text(vm.undoError ?? "")
        }
    }

    private var list: some View {
        ScrollView {
            LazyVStack(spacing: 10) {
                ForEach(vm.entries) { entry in
                    VStack(alignment: .leading, spacing: 8) {
                        ItineraryApplyHistoryRowView(entry: entry)
                            .opacity(vm.undoingID == entry.id ? 0.5 : 1)

                        if entry.isUndoable {
                            Button {
                                entryPendingUndo = entry
                            } label: {
                                Text("Geri Al")
                                    .font(.system(size: 13, weight: .semibold))
                                    .foregroundStyle(AppColors.destructive)
                                    .frame(maxWidth: .infinity)
                                    .padding(.vertical, 10)
                                    .background(AppColors.destructive.opacity(0.12))
                                    .clipShape(RoundedRectangle(cornerRadius: 12))
                            }
                            .buttonStyle(PressableButtonStyle())
                            .disabled(vm.undoingID != nil)
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
            Image(systemName: "clock.arrow.2.circlepath")
                .font(.system(size: 52))
                .foregroundStyle(AppColors.textTertiary)
            Text("Henüz uygulama geçmişi yok")
                .font(.system(size: 18, weight: .semibold))
                .foregroundStyle(AppColors.text)
            Text("Bir itinerary'i gezine uyguladığında,\nburada saklanır ve gerekirse geri alabilirsin.")
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
            Text(error.localizedDescription)
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
