import SwiftUI

/// `LibraryRowView`'ın seçim-modu görsel sözleşmesiyle BİREBİR aynı
/// (checkmark.circle.fill/circle çifti, accentText/textTertiary renkleri,
/// aynı kart/kenarlık stili) — Optimizer Yapılandırma ekranının kendi
/// mekan listesi için, ama `LibraryPlace` değil `TripStop` üzerinde çalışır.
struct TripStopSelectionRow: View {

    let stop:       TripStop
    let isSelected: Bool

    var body: some View {
        HStack(spacing: 14) {
            ZStack {
                RoundedRectangle(cornerRadius: 14)
                    .fill(AppColors.route.opacity(0.1))
                    .overlay(RoundedRectangle(cornerRadius: 14).stroke(AppColors.route.opacity(0.2)))
                Image(systemName: "mappin.circle.fill")
                    .font(.system(size: 22))
                    .foregroundStyle(AppColors.route)
            }
            .frame(width: 50, height: 50)

            VStack(alignment: .leading, spacing: 4) {
                Text(stop.name)
                    .font(.system(size: 14, weight: .semibold))
                    .foregroundStyle(AppColors.text)
                    .lineLimit(1)

                HStack(spacing: 8) {
                    if let category = stop.category, !category.isEmpty {
                        Text(category)
                            .font(.system(size: 11, weight: .medium))
                            .foregroundStyle(AppColors.route)
                            .padding(.horizontal, 8)
                            .padding(.vertical, 3)
                            .background(AppColors.route.opacity(0.1))
                            .clipShape(Capsule())
                    }
                    if let city = stop.city, !city.isEmpty {
                        Text(city)
                            .font(.system(size: 12))
                            .foregroundStyle(AppColors.textSecondary)
                    }
                }
            }

            Spacer()

            Image(systemName: isSelected ? "checkmark.circle.fill" : "circle")
                .font(.system(size: 20))
                .foregroundStyle(isSelected ? AppColors.accentText : AppColors.textTertiary)
        }
        .padding(14)
        .background(AppColors.surface)
        .clipShape(RoundedRectangle(cornerRadius: 18))
        .overlay(
            RoundedRectangle(cornerRadius: 18)
                .stroke(isSelected ? AppColors.accentText.opacity(0.5) : AppColors.border, lineWidth: 1)
        )
    }
}
