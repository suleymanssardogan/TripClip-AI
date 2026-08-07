import SwiftUI

struct TripRowView: View {

    let trip: TripSummary

    var body: some View {
        HStack(spacing: 14) {
            ZStack {
                RoundedRectangle(cornerRadius: 14)
                    .fill(AppColors.surface2)
                    .overlay(RoundedRectangle(cornerRadius: 14).stroke(AppColors.border))
                Image(systemName: "map.fill")
                    .font(.system(size: 20))
                    .foregroundStyle(AppColors.accentText)
            }
            .frame(width: 52, height: 52)

            VStack(alignment: .leading, spacing: 4) {
                Text(trip.title)
                    .font(.system(size: 15, weight: .semibold))
                    .foregroundStyle(AppColors.text)
                    .lineLimit(1)

                HStack(spacing: 10) {
                    Label("\(trip.stopsCount) durak", systemImage: "mappin")
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
        .padding(14)
        .background(AppColors.surface)
        .clipShape(RoundedRectangle(cornerRadius: 18))
        .overlay(
            RoundedRectangle(cornerRadius: 18)
                .stroke(AppColors.border, lineWidth: 1)
        )
    }
}
