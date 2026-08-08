import SwiftUI

/// Bir günün başlığı + sıralı, saatli durakları:
///   1. Gün
///   09:00  Colosseum          60 dk ziyaret
///   11:00  Roman Forum        45 dk ziyaret
struct ItineraryDaySection: View {
    let day: ItineraryDay

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("\(day.dayIndex + 1). Gün")
                .font(.system(size: 14, weight: .semibold))
                .foregroundStyle(AppColors.textSecondary)
                .textCase(.uppercase)
                .tracking(0.8)

            VStack(spacing: 8) {
                ForEach(day.stops) { stop in
                    ItineraryStopRow(stop: stop)
                }
            }
        }
    }
}

private struct ItineraryStopRow: View {
    let stop: ItineraryStop

    var body: some View {
        HStack(spacing: 12) {
            Text(stop.arrivalTime ?? "—")
                .font(.system(size: 13, weight: .bold, design: .rounded))
                .foregroundStyle(AppColors.route)
                .frame(width: 44, alignment: .leading)

            VStack(alignment: .leading, spacing: 2) {
                Text(stop.name)
                    .font(.system(size: 14, weight: .semibold))
                    .foregroundStyle(AppColors.text)
                Text("\(stop.visitDurationMinutes) dk ziyaret")
                    .font(.system(size: 12))
                    .foregroundStyle(AppColors.textSecondary)
            }

            Spacer()

            if let travelMinutes = stop.travelTimeToNextMinutes {
                VStack(alignment: .trailing, spacing: 2) {
                    Image(systemName: "arrow.turn.down.right")
                        .font(.system(size: 11))
                        .foregroundStyle(AppColors.textTertiary)
                    Text("\(Int(travelMinutes.rounded())) dk")
                        .font(.system(size: 11))
                        .foregroundStyle(AppColors.textTertiary)
                }
            }
        }
        .padding(12)
        .background(AppColors.surface)
        .clipShape(RoundedRectangle(cornerRadius: 14))
        .overlay(RoundedRectangle(cornerRadius: 14).stroke(AppColors.border, lineWidth: 1))
    }
}
