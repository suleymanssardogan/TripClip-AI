import SwiftUI

struct PlanRowView: View {

    let plan: PlanSummary

    var body: some View {
        HStack(spacing: 14) {
            VStack(alignment: .leading, spacing: 5) {
                Text(plan.displayTitle)
                    .font(.headline)
                    .foregroundStyle(AppColors.text)
                    .lineLimit(1)

                HStack(spacing: 10) {
                    Text("\(plan.locationsCount) mekan")
                        .font(.system(size: 12))
                        .foregroundStyle(AppColors.textSecondary)

                    if !plan.formattedDate.isEmpty {
                        Text(plan.formattedDate)
                            .font(.system(size: 12))
                            .foregroundStyle(AppColors.textSecondary)
                    }
                }
            }

            Spacer()

            statusBadge
        }
        .padding(16)
        .background(AppColors.surface)
        .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 16, style: .continuous)
                .stroke(AppColors.border, lineWidth: 1)
        )
    }

    @ViewBuilder
    private var statusBadge: some View {
        if plan.isCompleted {
            Image(systemName: "chevron.right")
                .font(.system(size: 12, weight: .semibold))
                .foregroundStyle(AppColors.textTertiary)
        } else {
            ProgressView()
                .tint(AppColors.warning)
                .accessibilityLabel("İşleniyor")
        }
    }

}
