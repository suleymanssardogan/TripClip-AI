import SwiftUI

/// Apply History listesindeki tek satır — `ItineraryHistoryRowView` ile
/// AYNI kart tarifi (leading badge + iki satır meta), yalnızca leading
/// badge'in içeriği skor yerine olay türünü (uygula/geri al) gösteren bir
/// ikon.
struct ItineraryApplyHistoryRowView: View {

    let entry: ApplyHistoryEntry

    private var badgeSymbol: String {
        entry.isUndo ? "arrow.uturn.backward" : "checkmark"
    }

    private var badgeColor: Color {
        entry.isUndo ? AppColors.warning : AppColors.success
    }

    /// Req "which itinerary was applied" — bkz. `ApplyHistoryEntry.itineraryId`
    /// doc yorumu: `nil`, `isUndo` ile birlikte İKİ farklı senaryoyu ayırt
    /// eder (itinerary sonradan silinmiş / geri alınan durum hiç
    /// itinerary-kökenli değildi) — kullanıcıya İKİSİ için de doğru,
    /// farklı bir metin gösterilir.
    private var title: String {
        if entry.itineraryId != nil {
            return entry.isUndo ? "Önceki itinerary'e dönüldü" : "Itinerary uygulandı"
        }
        return entry.isUndo ? "Manuel durak listesine dönüldü" : "Silinmiş optimizasyon"
    }

    var body: some View {
        HStack(spacing: 14) {
            ZStack {
                RoundedRectangle(cornerRadius: 14)
                    .fill(AppColors.surface2)
                    .overlay(RoundedRectangle(cornerRadius: 14).stroke(AppColors.border))
                Image(systemName: badgeSymbol)
                    .font(.system(size: 17, weight: .bold))
                    .foregroundStyle(badgeColor)
            }
            .frame(width: 52, height: 52)

            VStack(alignment: .leading, spacing: 4) {
                Text(title)
                    .font(.system(size: 14, weight: .semibold))
                    .foregroundStyle(AppColors.text)

                HStack(spacing: 10) {
                    if !entry.formattedAppliedAt.isEmpty {
                        Text(entry.formattedAppliedAt)
                            .font(.system(size: 12))
                            .foregroundStyle(AppColors.textSecondary)
                    }
                    if entry.isUndoable {
                        Label("Güncel", systemImage: "circle.fill")
                            .font(.system(size: 11, weight: .semibold))
                            .foregroundStyle(AppColors.accentText)
                    }
                }
            }

            Spacer()
        }
        .padding(14)
        .background(AppColors.surface)
        .clipShape(RoundedRectangle(cornerRadius: 18))
        .overlay(
            RoundedRectangle(cornerRadius: 18)
                .stroke(AppColors.border, lineWidth: 1)
        )
    }
}
