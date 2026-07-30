import SwiftUI

struct PlanRowView: View {

    let plan: PlanSummary

    var body: some View {
        HStack(spacing: 14) {
            // ── Location emoji ──────────────────────────────────────────────
            ZStack {
                RoundedRectangle(cornerRadius: 14)
                    .fill(AppColors.surface2)
                    .overlay(
                        RoundedRectangle(cornerRadius: 14)
                            .stroke(AppColors.border)
                    )
                Text(locationEmoji(for: plan.topLocation))
                    .font(.system(size: 26))
            }
            .frame(width: 52, height: 52)

            // ── Content ─────────────────────────────────────────────────────
            VStack(alignment: .leading, spacing: 4) {
                Text(plan.displayTitle)
                    .font(.system(size: 15, weight: .semibold))
                    .foregroundStyle(AppColors.text)
                    .lineLimit(1)

                HStack(spacing: 10) {
                    Label("\(plan.locationsCount) mekan", systemImage: "mappin")
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

            // ── Status badge ────────────────────────────────────────────────
            statusBadge
        }
        .padding(14)
        .background(AppColors.surface)
        .clipShape(RoundedRectangle(cornerRadius: 18))
        .overlay(
            RoundedRectangle(cornerRadius: 18)
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
            HStack(spacing: 4) {
                Circle()
                    .fill(AppColors.warning)
                    .frame(width: 6, height: 6)
                    .overlay(Circle().fill(AppColors.warning).scaleEffect(1.5).opacity(0.3))
                Text("İşleniyor")
                    .font(.system(size: 11, weight: .medium))
                    .foregroundStyle(AppColors.warning)
            }
            .padding(.horizontal, 10)
            .padding(.vertical, 5)
            .background(AppColors.warning.opacity(0.1))
            .clipShape(Capsule())
        }
    }

    private func locationEmoji(for location: String?) -> String {
        guard let loc = location?.lowercased() else { return "🗺️" }
        let map: [String: String] = [
            "istanbul": "🕌", "ankara": "🏛️", "izmir": "🏖️",
            "antalya": "🏝️", "kapadokya": "🎈", "trabzon": "⛰️",
            "bodrum": "⛵", "mardin": "🌙", "bursa": "🏔️",
        ]
        return map.first(where: { loc.contains($0.key) })?.value ?? "📍"
    }
}
