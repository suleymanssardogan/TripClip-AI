import SwiftUI

struct LocationCard: View {

    /// Ekranda gösterilen sıra numarası. `pin.index` DEĞİL: o, sunucudaki
    /// kalıcı durak kimliği ve kullanıcı bir durağı sildiğinde boşluk bırakıyor
    /// (1, 2, 4, …). Görünen numara her zaman listedeki pozisyondan üretilir.
    let number: Int
    let pin: LocationPin
    /// Düzenleme modu kontrolleri. nil ise kart normal görünümde.
    var edit: EditActions? = nil
    /// Şu an haritada/itinerary'de odaklanılan durak mı — bkz.
    /// `TripDetailView`'ın `OptimizerSelection` kullanımı. Varsayılan
    /// `false`: `ResultsView`'ın kendi kullanımı bu parametreyi hiç
    /// GEÇMİYOR, geriye dönük UYUMLU.
    var isSelected: Bool = false

    struct EditActions {
        let canMoveUp:   Bool
        let canMoveDown: Bool
        let onMoveUp:    () -> Void
        let onMoveDown:  () -> Void
        let onDelete:    () -> Void
    }

    var body: some View {
        HStack(spacing: 12) {
            // Index badge
            ZStack {
                Circle()
                    .fill(AppColors.route.opacity(0.15))
                    .overlay(Circle().stroke(AppColors.route.opacity(0.3)))
                Text("\(number)")
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

            if let edit {
                editControls(edit)
            } else {
                // Seçili durumda dolu ikon + accent renk — yalnızca renkle
                // değil, ŞEKİLLE de iletilir (dolu/boş daire), `ItineraryStopRow`
                // ile AYNI ilke (bkz. docs/web-trip-optimizer.md'nin web
                // karşılığı, "selected state is not communicated only through
                // color").
                Image(systemName: isSelected ? "mappin.circle.fill" : "mappin.circle")
                    .font(.system(size: 16))
                    .foregroundStyle(isSelected ? AppColors.accentText : AppColors.route.opacity(0.6))
            }
        }
        .padding(12)
        .background(isSelected ? AppColors.accent.opacity(0.12) : AppColors.surface)
        .clipShape(RoundedRectangle(cornerRadius: 14))
        .overlay(
            RoundedRectangle(cornerRadius: 14)
                .stroke(isSelected ? AppColors.accent : AppColors.border, lineWidth: isSelected ? 2 : 1)
        )
    }

    /// Sürükle-bırak yerine yukarı/aşağı düğmeleri: liste `List` değil
    /// `LazyVStack` içinde özel kartlarla çiziliyor, `.onMove` kullanılamıyor.
    private func editControls(_ edit: EditActions) -> some View {
        HStack(spacing: 4) {
            Button(action: edit.onMoveUp) {
                Image(systemName: "chevron.up")
                    .font(.system(size: 13, weight: .semibold))
                    .frame(width: 30, height: 30)
            }
            .disabled(!edit.canMoveUp)
            .foregroundStyle(edit.canMoveUp ? AppColors.textSecondary : AppColors.textTertiary)
            // Sembol-yalnızca düğmeler VoiceOver'a yalnızca genel SF Symbol
            // adını ("chevron up") anons eder, EYLEMİ değil (M35 audit
            // bulgusu) — bu, VoiceOver kullanıcısının bir durağı yeniden
            // sıralayabileceği/silebileceği TEK yol olduğu için önemli.
            .accessibilityLabel("Yukarı taşı")

            Button(action: edit.onMoveDown) {
                Image(systemName: "chevron.down")
                    .font(.system(size: 13, weight: .semibold))
                    .frame(width: 30, height: 30)
            }
            .disabled(!edit.canMoveDown)
            .foregroundStyle(edit.canMoveDown ? AppColors.textSecondary : AppColors.textTertiary)
            .accessibilityLabel("Aşağı taşı")

            Button(action: edit.onDelete) {
                Image(systemName: "trash")
                    .font(.system(size: 13, weight: .semibold))
                    .frame(width: 30, height: 30)
            }
            .foregroundStyle(AppColors.destructive)
            .accessibilityLabel("Durağı sil")
        }
        .buttonStyle(.plain)
    }
}
