import SwiftUI

struct LibraryRowView: View {

    let place: LibraryPlace
    /// nil → normal görünüm (Düzenle/Seç modu kapalı). Değer varsa Trip Builder
    /// seçim modu açık ve bu satırın seçili olup olmadığını gösterir.
    var isSelected: Bool? = nil

    var body: some View {
        HStack(spacing: 14) {
            VStack(alignment: .leading, spacing: 4) {
                Text(place.name)
                    .font(.headline)
                    .foregroundStyle(AppColors.text)
                    .lineLimit(1)

                HStack(spacing: 8) {
                    if let category = place.category, !category.isEmpty {
                        Text(category)
                            .font(.subheadline)
                            .foregroundStyle(AppColors.textSecondary)
                    }
                    if let city = place.city, !city.isEmpty {
                        Text(city)
                            .font(.system(size: 12))
                            .foregroundStyle(AppColors.textSecondary)
                    }
                    // Birden çok Reels'ten çıkarılan bir mekan — kullanıcı
                    // veya farklı kullanıcılar aynı yeri birden çok kez
                    // "keşfetmiş" demek, dikkat çekmeye değer bir sinyal.
                    if place.saveCount > 1 {
                        Label("\(place.saveCount)", systemImage: "bookmark.fill")
                            .font(.system(size: 11, weight: .medium))
                            .foregroundStyle(AppColors.accentText)
                    }
                }
            }

            Spacer()

            if let isSelected {
                Image(systemName: isSelected ? "checkmark.circle.fill" : "circle")
                    .font(.system(size: 20))
                    .foregroundStyle(isSelected ? AppColors.accentText : AppColors.textTertiary)
            } else {
                Image(systemName: "chevron.right")
                    .font(.system(size: 12, weight: .semibold))
                    .foregroundStyle(AppColors.textTertiary)
            }
        }
        .padding(14)
        .background(AppColors.surface)
        .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 16, style: .continuous)
                .stroke(isSelected == true ? AppColors.accentText.opacity(0.5) : AppColors.border, lineWidth: 1)
        )
        // Seçim modu açıkken (isSelected != nil), seçili durum daireyi
        // doldurup renk değiştirerek GÖRSEL olarak iletiliyordu ama
        // VoiceOver'a hiç aktarılmıyordu — kullanıcı hangi mekanların
        // seçili olduğunu duyamıyordu (M35 audit bulgusu). `TripDetailView`'ın
        // gün çipi/`OptimizerRouteMapSection`'ın kendi `.isSelected` trait
        // deseniyle AYNI.
        .accessibilityElement(children: isSelected != nil ? .combine : .contain)
        .accessibilityAddTraits(isSelected == true ? [.isSelected] : [])
    }
}
