import SwiftUI

/// Optimizer uyarıları — "açılış saatleri bilinmiyor", "uzun seyahat segmenti",
/// "tekrarlı mekan seçimi kaldırıldı" gibi core-api mesajları olduğu gibi
/// gösterilir (bkz. GreedyDistanceStrategy). Sonuç listesinden görsel olarak
/// AYRIK tutulur (spesifikasyonun gereksinimi) — kendi kartı, kendi rengi.
struct ItineraryWarningsSection: View {
    let warnings: [String]

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Label("Uyarılar", systemImage: "exclamationmark.triangle.fill")
                .font(.system(size: 13, weight: .semibold))
                .foregroundStyle(AppColors.warning)
                .textCase(.uppercase)
                .tracking(0.6)

            VStack(alignment: .leading, spacing: 8) {
                ForEach(Array(warnings.enumerated()), id: \.offset) { _, warning in
                    HStack(alignment: .top, spacing: 8) {
                        Circle()
                            .fill(AppColors.warning)
                            .frame(width: 5, height: 5)
                            .padding(.top, 6)
                        Text(warning)
                            .font(.system(size: 13))
                            .foregroundStyle(AppColors.text)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                }
            }
        }
        .padding(14)
        .background(AppColors.warning.opacity(0.1))
        .clipShape(RoundedRectangle(cornerRadius: 14))
        .overlay(RoundedRectangle(cornerRadius: 14).stroke(AppColors.warning.opacity(0.3), lineWidth: 1))
    }
}
