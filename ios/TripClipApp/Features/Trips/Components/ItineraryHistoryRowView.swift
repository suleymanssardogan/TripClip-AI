import SwiftUI

/// Itinerary History listesindeki tek satır — TripRowView ile aynı kart
/// tarifi (leading badge + iki satır meta + chevron), yalnızca leading
/// badge'in içeriği ikon yerine skor sayısı.
struct ItineraryHistoryRowView: View {

    let summary: ItinerarySummary

    private var scoreColor: Color {
        switch summary.optimizationScore {
        case 80...:   return AppColors.success
        case 50..<80: return AppColors.warning
        default:      return AppColors.destructive
        }
    }

    var body: some View {
        HStack(spacing: 14) {
            ZStack {
                RoundedRectangle(cornerRadius: 14)
                    .fill(AppColors.surface2)
                    .overlay(RoundedRectangle(cornerRadius: 14).stroke(AppColors.border))
                Text("\(Int(summary.optimizationScore.rounded()))")
                    .font(.system(size: 17, weight: .bold, design: .rounded))
                    .foregroundStyle(scoreColor)
            }
            .frame(width: 52, height: 52)

            VStack(alignment: .leading, spacing: 4) {
                HStack(spacing: 10) {
                    Label("\(summary.daysCount) gün", systemImage: "calendar")
                    Label("\(summary.stopsCount) durak", systemImage: "mappin")
                }
                .font(.system(size: 12))
                .foregroundStyle(AppColors.textSecondary)

                HStack(spacing: 10) {
                    if !summary.formattedCreatedAt.isEmpty {
                        Text(summary.formattedCreatedAt)
                            .font(.system(size: 12))
                            .foregroundStyle(AppColors.textSecondary)
                    }
                    if !summary.warnings.isEmpty {
                        Label("\(summary.warnings.count) uyarı", systemImage: "exclamationmark.triangle.fill")
                            .font(.system(size: 12, weight: .semibold))
                            .foregroundStyle(AppColors.warning)
                    }
                }
            }

            Spacer()

            Image(systemName: "chevron.right")
                .font(.system(size: 12, weight: .semibold))
                .foregroundStyle(AppColors.textTertiary)
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
