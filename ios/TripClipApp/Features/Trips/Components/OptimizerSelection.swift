import Foundation

/// `TripOptimizerView`'ın harita (`OptimizerRouteMapSection`) ve itinerary
/// listesi (`ItineraryDaySection`) arasında PAYLAŞTIĞI TEK seçim durumu
/// (Req 13) — ikisi de kendi otoriter kopyasını icat etmez; `TripOptimizerView`
/// sahiplenir, her ikisine de bu tür üzerinden (binding/parametre) geçirilir.
///
/// `stopID`, `ItineraryStop.id`/`OptimizerMapStop.id` ile AYNI kararlı kimlik
/// uzayını kullanır (bkz. o tiplerin kendi doc yorumları — ikisi de sunucunun
/// `day_index-order_index-place_id` üçlüsünden türetilir). Array index'e
/// ASLA dayanmaz, bu yüzden gün seçimi değişse, harita verisi yeniden
/// üretilse (`OptimizerRouteMapData` her `OptimizerRouteMapSection.init`'te
/// baştan hesaplanır) ya da itinerary geçmişten yüklenmiş olsa bile aynı
/// durağı güvenilir biçimde tanımlar (Req 3).
struct OptimizerSelection: Equatable {
    /// nil = "Tümü" (tüm günler) — day selector'ın v5'ten beri süregelen
    /// semantiği, bu milestone'da değişmedi.
    var dayIndex: Int?
    /// Şu an haritada odaklanılan / itinerary listesinde vurgulanan durak.
    var stopID: String?
}

extension OptimizerSelection {
    /// Bir durağa (haritadan ya da itinerary listesinden) dokunulduğunda
    /// oluşacak yeni seçim. Req 1 ("preserve the current selected day") ve
    /// Req 4 ("switch to that day if the tapped stop belongs to another
    /// day") TEK bir kuralda birleşir: yeni seçim HER ZAMAN dokunulan
    /// durağın kendi gününe ayarlanır —
    ///   - dokunulan durak zaten aktif günün içindeyse `dayIndex` değişmez
    ///     (görünürde "korunmuş" olur, `OptimizerRouteMapSection`'ın
    ///     `.task(id: selection.dayIndex)` YENİDEN TETİKLENMEZ → Req 1/5/6
    ///     "do not recalculate the route merely because a stop was
    ///     selected"),
    ///   - başka bir güne aitse `dayIndex` o güne döner (Req 4 "switch to
    ///     that day"), bu durumda `.task(id:)` gerçekten değiştiği için
    ///     haklı olarak yeniden tetiklenir (Req 5'in kendi istisnası:
    ///     "unless the selected day actually changes").
    static func focusing(dayIndex: Int, stopID: String) -> OptimizerSelection {
        OptimizerSelection(dayIndex: dayIndex, stopID: stopID)
    }
}
