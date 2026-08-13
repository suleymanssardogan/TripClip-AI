import SwiftUI

/// Bir günün başlığı + sıralı, saatli durakları:
///   1. Gün                            (start_date verilmediyse)
///   12 Ağustos 2026                   (start_date verildiyse — bkz. `ItineraryDay.formattedDate`)
///   09:00  Colosseum          60 dk ziyaret
///   11:00  Roman Forum        45 dk ziyaret
///
/// Harita ile PAYLAŞILAN tek seçimin (bkz. `OptimizerSelection`) salt-okunur
/// izdüşümünü alır — kendi otoriter seçim state'ini icat etmez (Req 13).
/// Bir durağa dokunmak `onSelectStop` üzerinden üst katmana (`TripOptimizerView`)
/// bildirilir; hem state güncellemesi hem haritayı görünür kılacak kaydırma
/// TEK bir yerde (aynı `ScrollViewReader` proxy'sini paylaşan üst katmanda)
/// yaşar, burada tekrarlanmaz.
struct ItineraryDaySection: View {
    let day: ItineraryDay
    /// Şu an haritada/itinerary'de odaklanılan durağın kimliği — `ItineraryStop.id`
    /// ile karşılaştırılır (Req 3: array index'e ASLA dayanmaz).
    var selectedStopID: String? = nil
    var onSelectStop: ((ItineraryStop) -> Void)? = nil

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            // Req: "günler yalnızca sıra numarasıyla DEĞİL, gerçek takvim
            // günleriyle gösterilebilsin" — start_date verilmişse
            // `formattedDate` "12 Ağustos 2026" döner; verilmemişse (bu
            // milestone'dan önceki her itinerary dahil) `nil` döner ve
            // eski "N. Gün" etiketine düşülür (Req 4: geriye dönük uyumlu).
            Text(day.formattedDate ?? "\(day.dayIndex + 1). Gün")
                .font(.system(size: 14, weight: .semibold))
                .foregroundStyle(AppColors.textSecondary)
                .textCase(.uppercase)
                .tracking(0.8)

            VStack(spacing: 8) {
                ForEach(day.stops) { stop in
                    Button {
                        onSelectStop?(stop)
                    } label: {
                        ItineraryStopRow(stop: stop, isSelected: stop.id == selectedStopID)
                    }
                    .buttonStyle(PressableButtonStyle())
                    .id(Self.rowID(for: stop.id))
                }
            }
        }
    }

    /// `stop.id` tabanlı, kararlı bir `ScrollViewReader` hedefi — harita bir
    /// durağı bildirdiğinde `TripOptimizerView` bu id'ye kaydırır. Koordinatı
    /// olmayan bir durak dahil, HER durak için tanımlıdır (Req 9: harita
    /// verisinde yoksa bile itinerary listesinde seçilebilir kalır).
    static func rowID(for stopID: String) -> String { "optimizer-itinerary-stop-\(stopID)" }
}

private struct ItineraryStopRow: View {
    let stop: ItineraryStop
    var isSelected: Bool = false

    var body: some View {
        HStack(spacing: 12) {
            Text(stop.arrivalTime ?? "—")
                .font(.system(size: 13, weight: .bold, design: .rounded))
                .foregroundStyle(AppColors.route)
                .frame(width: 44, alignment: .leading)

            VStack(alignment: .leading, spacing: 2) {
                Text(stop.name)
                    .font(.system(size: 14, weight: .semibold))
                    .foregroundStyle(AppColors.text)
                Text("\(stop.visitDurationMinutes) dk ziyaret")
                    .font(.system(size: 12))
                    .foregroundStyle(AppColors.textSecondary)
            }

            Spacer()

            if let travelMinutes = stop.travelTimeToNextMinutes {
                VStack(alignment: .trailing, spacing: 2) {
                    Image(systemName: "arrow.turn.down.right")
                        .font(.system(size: 11))
                        .foregroundStyle(AppColors.textTertiary)
                    Text("\(Int(travelMinutes.rounded())) dk")
                        .font(.system(size: 11))
                        .foregroundStyle(AppColors.textTertiary)
                }
            }
        }
        .padding(12)
        .background(isSelected ? AppColors.accent.opacity(0.12) : AppColors.surface)
        .clipShape(RoundedRectangle(cornerRadius: 14))
        .overlay(
            RoundedRectangle(cornerRadius: 14)
                .stroke(isSelected ? AppColors.accent : AppColors.border, lineWidth: isSelected ? 2 : 1)
        )
        // Seçili durum dolu/boş renk+kenarlıkla GÖRSEL olarak iletiliyordu
        // (bkz. yukarıdaki doc yorumu — "not just color") ama VoiceOver'a
        // hiç aktarılmıyordu (M35 audit bulgusu). `TripAssistantView`'ın
        // mesaj baloncuklarındaki combine+label deseniyle AYNI.
        .accessibilityElement(children: .combine)
        .accessibilityLabel("\(stop.arrivalTime ?? ""), \(stop.name), \(stop.visitDurationMinutes) dakika ziyaret")
        .accessibilityAddTraits(isSelected ? [.isSelected] : [])
    }
}
