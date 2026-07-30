import SwiftUI

struct LocationCard: View {

    let pin: LocationPin

    var body: some View {
        HStack(spacing: 12) {
            // Index badge
            ZStack {
                Circle()
                    .fill(AppColors.route.opacity(0.15))
                    .overlay(Circle().stroke(AppColors.route.opacity(0.3)))
                Text("\(pin.index)")
                    .font(.system(size: 13, weight: .bold, design: .rounded))
                    .foregroundStyle(AppColors.route)
            }
            .frame(width: 34, height: 34)

            VStack(alignment: .leading, spacing: 2) {
                Text(pin.name)
                    .font(.system(size: 14, weight: .semibold))
                    .foregroundStyle(AppColors.text)
                Text(pin.type.capitalized)
                    .font(.system(size: 12))
                    .foregroundStyle(AppColors.textSecondary)
            }

            Spacer()

            Image(systemName: "mappin.circle")
                .font(.system(size: 16))
                .foregroundStyle(AppColors.route.opacity(0.6))
        }
        .padding(12)
        .background(AppColors.surface)
        .clipShape(RoundedRectangle(cornerRadius: 14))
        .overlay(
            RoundedRectangle(cornerRadius: 14)
                .stroke(AppColors.border, lineWidth: 1)
        )
    }
}
