import SwiftUI

struct TripRowView: View {

    let trip: TripSummary

    var body: some View {
        HStack(spacing: 14) {
            VStack(alignment: .leading, spacing: 5) {
                Text(trip.title)
                    .font(.headline)
                    .foregroundStyle(AppColors.text)
                    .lineLimit(1)

                HStack(spacing: 10) {
                    Text("\(trip.stopsCount) durak")
                        .font(.system(size: 12))
                        .foregroundStyle(AppColors.textSecondary)

                    if !trip.formattedCreatedAt.isEmpty {
                        Text(trip.formattedCreatedAt)
                            .font(.system(size: 12))
                            .foregroundStyle(AppColors.textSecondary)
                    }
                }
            }

            Spacer()

            Image(systemName: "chevron.right")
                .font(.system(size: 12, weight: .semibold))
                .foregroundStyle(AppColors.textTertiary)
        }
        .padding(16)
        .background(AppColors.surface)
        .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 16, style: .continuous)
                .stroke(AppColors.border, lineWidth: 1)
        )
    }
}
