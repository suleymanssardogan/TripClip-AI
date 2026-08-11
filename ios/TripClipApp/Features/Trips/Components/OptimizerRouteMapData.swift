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
    /// Sahibi `Itinerary.id` — bu günün HANGİ itinerary'e ait olduğu
    /// (Persistent Optimizer Route Cache milestone'unda eklendi). Rota
    /// önbellek anahtarının bir parçası (bkz. `OptimizerRouteCalculator.
    /// legKey`/`cacheKey`): `dayIndex` + durak listesi TEK BAŞINA iki farklı
    /// itinerary'yi ayırt etmeye yetmez (aynı yerleri içeren iki itinerary
    /// aynı gün+durak diziliminde bitebilir; `ItineraryStop.id` de bir
    /// itinerary çalıştırması boyunca sabit bir kimlik DEĞİL, yalnızca
    /// "gün-sıra-place" biçimi — bkz. `ItineraryStop.id` doc yorumu). Test
    /// fixture'larının çoğu itinerary izolasyonuyla ilgilenmediğinden
    /// varsayılan `0` — yalnızca `OptimizerRouteMapData.init(itinerary:)`
    /// gerçek `itinerary.id`'yi açıkça geçirir.
    let itineraryID: Int
    /// `ItineraryDay.date` ile AYNI alan (`"YYYY-MM-DD"`, itinerary'nin
    /// `start_date`'i verildiyse) — haritanın gün seçici çipleri için
    /// buraya da taşınıyor (bkz. `chipLabel`). Verilmediyse `nil`.
    let date:     String?
    /// `ItineraryStop.orderIndex` sırasına göre, yalnızca koordinatlı duraklar.
    let stops:    [OptimizerMapStop]

    // Elle yazılmış, `date` için varsayılan değerli bir memberwise init —
    // property'nin kendi bildirimine `= nil` eklemek yerine burada (bkz.
    // `ItineraryDay`'in AYNI tuzağı, OptimizerModels.swift): bir `let`
    // property'ye satır-içi varsayılan değer vermek onu HEM `Decodable`
    // sentezinden HEM sentezlenen memberwise init'ten sessizce hariç
    // tutuyor — `date: String? = nil` yazınca "extra argument 'date' in
    // call" hatasıyla karşılaşıldı (bu tür Decodable olmasa bile). Elle
    // yazılmış bu init o sentez mekanizmalarına hiç dokunmuyor, yalnızca
    // eski (v9 öncesi) test fixture'larının `date`/`itineraryID`
    // belirtmeden derlenmeye devam etmesini sağlıyor.
    init(dayIndex: Int, itineraryID: Int = 0, date: String? = nil, stops: [OptimizerMapStop]) {
        self.dayIndex = dayIndex
        self.itineraryID = itineraryID
        self.date = date
        self.stops = stops
    }

    var id: Int { dayIndex }
}

extension OptimizerMapDay {
    /// Gün seçici çipinin GÖRÜNEN metni — tarih varsa `"12 Ağustos"` (yıl
    /// YOK; `ItineraryDay.formattedDate`'in `"12 Ağustos 2026"`'sından daha
    /// kısa, çipin dar alanı için), yoksa `"N. Gün"` (geriye dönük uyumluluk
    /// — tarihsiz/eski itinerary'ler, bkz. docs/ios-trip-optimizer.md
    /// "Date-aware Map Day Selector"). Backend'in zaten ürettiği değer
    /// yalnızca gösteriliyor — burada HİÇBİR takvim aritmetiği yok.
    var chipLabel: String {
        parsedShortDate ?? "\(dayIndex + 1). Gün"
    }

    /// VoiceOver etiketi — hem sıra numarası hem tarih (varsa) birlikte,
    /// yalnızca görünen kısa metinden daha bilgilendirici (bkz.
    /// docs/ios-trip-optimizer.md "Date-aware Map Day Selector →
    /// Accessibility").
    var chipAccessibilityLabel: String {
        if let parsedShortDate {
            return "\(dayIndex + 1). gün, \(parsedShortDate)"
        }
        return "\(dayIndex + 1). gün"
    }

    /// `date` (`"YYYY-MM-DD"`) ayrıştırılıp `"12 Ağustos"` biçimine
    /// çevrilmiş hâli — `chipLabel`/`chipAccessibilityLabel` arasında
    /// TEKRARLANMASIN diye tek bir yerde. `date` eksikse ya da (teorik
    /// olarak, backend zaten doğruluyor) ayrıştırılamayan bir biçimdeyse
    /// `nil` — her iki çağıran taraf da bu durumda kendi geriye dönük
    /// uyumlu düşüşüne sahip.
    private var parsedShortDate: String? {
        guard let date, let parsed = APIDate.parseDateOnly(date) else { return nil }
        return APIDate.shortDisplayString(from: parsed)
    }
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
                days.append(OptimizerMapDay(
                    dayIndex: day.dayIndex, itineraryID: itinerary.id, date: day.date, stops: stops
                ))
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
