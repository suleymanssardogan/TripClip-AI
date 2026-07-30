import SwiftUI

struct TravelTipsSection: View {

    let tips: [TravelTip]

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Label("Seyahat İpuçları", systemImage: "lightbulb.fill")
                .font(.system(size: 15, weight: .semibold))
                .foregroundStyle(AppColors.text)

            ForEach(Array(tips.enumerated()), id: \.offset) { _, tip in
                TipRow(tip: tip)
            }
        }
    }
}

private struct TipRow: View {
    let tip: TravelTip

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            if !tip.location.isEmpty {
                Text(tip.location)
                    .font(.system(size: 11, weight: .semibold))
                    .foregroundStyle(AppColors.accentText)
                    .textCase(.uppercase)
                    .tracking(0.5)
            }
            Text(tip.tip)
                .font(.system(size: 13))
                .foregroundStyle(AppColors.textSecondary)
                .fixedSize(horizontal: false, vertical: true)
        }
        .padding(12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(AppColors.surface)
        .clipShape(RoundedRectangle(cornerRadius: 12))
        .overlay(
            RoundedRectangle(cornerRadius: 12)
                .stroke(AppColors.accent.opacity(0.12), lineWidth: 1)
        )
    }
}
