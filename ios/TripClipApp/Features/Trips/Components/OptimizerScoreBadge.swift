import SwiftUI

/// Optimizasyon skoru + özet istatistikler. TripDetailView.statsStrip ile
/// aynı 3-hücreli, ayraçlı görsel tarif — skor hücresi renk kodlu (yeşil/
/// amber/kırmızı) ilk hücre olarak eklenir. Skor core-api'de hesaplanır
/// (GreedyDistanceStrategy — seyahat mesafesi + uyarı sayısına göre 0-100),
/// burada yalnızca gösterilir.
struct OptimizerScoreBadge: View {
    let score:              Double
    let totalDistanceKm:    Double
    let totalTravelMinutes: Double

    private var scoreColor: Color {
        switch score {
        case 80...:    return AppColors.success
        case 50..<80:  return AppColors.warning
        default:       return AppColors.destructive
        }
    }

    var body: some View {
        HStack(spacing: 0) {
            VStack(spacing: 2) {
                Text("\(Int(score.rounded()))")
                    .font(.system(size: 28, weight: .bold, design: .rounded))
                    .foregroundStyle(scoreColor)
                Text("Skor")
                    .font(.system(size: 11))
                    .foregroundStyle(AppColors.textSecondary)
            }
            .frame(maxWidth: .infinity)

            Divider().frame(height: 36).background(AppColors.border)
            statCell(icon: "arrow.triangle.swap", value: distanceString, label: "Mesafe")
            Divider().frame(height: 36).background(AppColors.border)
            statCell(icon: "clock", value: travelTimeString, label: "Seyahat")
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

    private var distanceString: String { String(format: "%.1f km", totalDistanceKm) }

    private var travelTimeString: String {
        let minutes = Int(totalTravelMinutes.rounded())
        guard minutes >= 60 else { return "\(minutes) dk" }
        return "\(minutes / 60)s \(minutes % 60)dk"
    }
}
