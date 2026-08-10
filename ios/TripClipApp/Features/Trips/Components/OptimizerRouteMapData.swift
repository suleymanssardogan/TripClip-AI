import Foundation

/// Bir itinerary durağının haritada çizilebilir hâli — yalnızca lat/lng'i
/// olan duraklar için üretilir (bkz. `OptimizerRouteMapData.init`).
/// `orderIndex` sunucunun belirlediği gerçek optimizer sırasıdır (0-based);
/// koordinatsız bir durak atlandığında bu sırada boşluk kalabilir — sıra
/// numaraları o yüzden ekranda gösterilen konumdan değil, bu alandan üretilir.
struct OptimizerMapStop: Identifiable, Hashable {
    let id:         String
    let dayIndex:   Int
    let orderIndex: Int
    let name:       String
    let latitude:   Double
    let longitude:  Double
}

struct OptimizerMapDay: Identifiable, Hashable {
    let dayIndex: Int
    /// `ItineraryStop.orderIndex` sırasına göre, yalnızca koordinatlı duraklar.
    let stops:    [OptimizerMapStop]

    var id: Int { dayIndex }
}

/// `Itinerary` → harita için güne göre bölünmüş, yalnızca koordinatlı
/// durakları içeren sunum verisi. MapKit'e bağımlı değil (saf Foundation
/// dönüşümü) — harita çizimini test etmek zor olduğundan bu eşleme ayrı,
/// MapKit'siz test edilebilir (bkz. docs/ios-trip-optimizer.md "Map view").
struct OptimizerRouteMapData: Hashable {
    /// Yalnızca en az bir koordinatlı durağı olan günler.
    let days: [OptimizerMapDay]
    /// Koordinatı olmadığı için haritadan atlanan toplam durak sayısı —
    /// mekanlar metinsel itinerary'de her zaman görünmeye devam eder,
    /// yalnızca haritada gösterilemezler (Req 7: konum uydurulmaz).
    let missingCoordinateCount: Int

    init(itinerary: Itinerary) {
        var days: [OptimizerMapDay] = []
        var missing = 0

        for day in itinerary.days {
            var stops: [OptimizerMapStop] = []
            for stop in day.stops {
                guard let lat = stop.lat, let lng = stop.lng else {
                    missing += 1
                    continue
                }
                stops.append(OptimizerMapStop(
                    id: stop.id, dayIndex: day.dayIndex, orderIndex: stop.orderIndex,
                    name: stop.name, latitude: lat, longitude: lng
                ))
            }
            if !stops.isEmpty {
                days.append(OptimizerMapDay(dayIndex: day.dayIndex, stops: stops))
            }
        }

        self.days = days
        self.missingCoordinateCount = missing
    }

    var isEmpty:           Bool { days.isEmpty }
    var hasMultipleDays:   Bool { days.count > 1 }
    var allStops: [OptimizerMapStop] { days.flatMap(\.stops) }

    /// `selectedDayIndex` nil ise tüm günler döner (her biri kendi rengiyle
    /// ayrık kalır); belirli bir gün seçiliyse yalnızca o günün durakları —
    /// böylece bir günün son durağı ile ertesi günün ilk durağı ASLA aynı
    /// rotada birleşmez (Req 2).
    func visibleDays(selectedDayIndex: Int?) -> [OptimizerMapDay] {
        guard let selectedDayIndex else { return days }
        return days.filter { $0.dayIndex == selectedDayIndex }
    }

    /// `stopID` (bkz. `OptimizerSelection.stopID`) ile eşleşen haritalanmış
    /// durağı bulur. Koordinatı olmayan bir durak `init`'te zaten elendiği
    /// için burada da bulunamaz — bu, "haritada odaklanacak bir şey yok"
    /// durumunu MapKit'e hiç dokunmadan, saf/test edilebilir biçimde temsil
    /// eder (Req 9: geçersiz bir koordinata asla merkezlenmez, çünkü arayan
    /// taraf bu `nil`'i görüp hiçbir kamera işlemi yapmaz — bkz.
    /// `OptimizerRouteMap.updateUIView`).
    func stop(withID stopID: String) -> OptimizerMapStop? {
        allStops.first { $0.id == stopID }
    }
}
