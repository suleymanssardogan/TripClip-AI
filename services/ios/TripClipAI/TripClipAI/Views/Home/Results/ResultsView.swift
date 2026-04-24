import SwiftUI
import MapKit
import UniformTypeIdentifiers

// MARK: - Ana View

struct ResultsView: View {
    let videoId: Int
    var preloadedData: AIResults? = nil

    @Environment(\.dismiss) private var dismiss

    @State private var videoData: VideoResponse?
    @State private var isLoading = true
    @State private var errorMessage: String?
    @State private var selectedLocation: EnrichedLocation?
    @State private var showShareSheet = false
    @State private var showInstagramShare = false
    @State private var pdfData: Data?
    @State private var shareImage: UIImage?

    // Gerçek zamanlı ilerleme (Redis polling)
    @State private var progressStage: String = "metadata"
    @State private var progressPercent: Int = 5
    @State private var elapsedSeconds: Int = 0
    @State private var elapsedTimer: Timer?

    // Aşama → (ikon, Türkçe metin)
    static let stageMap: [String: (icon: String, text: String)] = [
        "metadata":    ("doc.text.fill",           "Video bilgileri okunuyor..."),
        "frames":      ("film.stack",              "Kareler çıkarılıyor..."),
        "ai_parallel": ("eye.fill",                "Görüntü ve ses AI ile analiz ediliyor..."),
        "ner":         ("brain.head.profile",      "Yer isimleri tanımlanıyor..."),
        "ner_ocr":     ("text.viewfinder",         "Tabelalar filtreleniyor..."),
        "geocoding":   ("mappin.and.ellipse",      "Koordinatlar bulunuyor..."),
        "overpass":    ("map.fill",                "Harita verileri sorgulanıyor..."),
        "dedup":       ("checkmark.seal.fill",     "Mekanlar temizleniyor..."),
        "route":       ("point.3.filled.connected.trianglepath.dotted", "Rota optimize ediliyor..."),
        "rag":         ("sparkles",                "Seyahat ipuçları oluşturuluyor..."),
    ]

    var currentStageInfo: (icon: String, text: String) {
        ResultsView.stageMap[progressStage] ?? ("cpu.fill", "İşleniyor...")
    }

    var body: some View {
        ZStack {
            // Arka plan gradyanı
            LinearGradient(
                colors: [Color(hex: "0A0E1A"), Color(hex: "0d1f35")],
                startPoint: .topLeading, endPoint: .bottomTrailing
            )
            .ignoresSafeArea()

            if isLoading {
                analysisLoadingView
            } else if let video = videoData {
                resultsContent(video: video)
            } else if let error = errorMessage {
                errorView(message: error)
            }
        }
        .navigationTitle("Gezi Analizi")
        .navigationBarTitleDisplayMode(.inline)
        .toolbarColorScheme(.dark, for: .navigationBar)
        .toolbar {
            if let video = videoData {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Menu {
                        // Instagram Stories'e direkt paylaş
                        Button {
                            shareToInstagramStories(image: TripShareCard.render(video: video))
                        } label: {
                            Label("Instagram Story'de Paylaş", systemImage: "camera.filters")
                        }

                        // Sistem share sheet (her uygulamaya)
                        Button {
                            shareImage = TripShareCard.render(video: video)
                            showShareSheet = true
                        } label: {
                            Label("Görsel Olarak Paylaş", systemImage: "photo")
                        }

                        Button {
                            pdfData = PDFExportService.generateTripPDF(video: video)
                            shareImage = nil
                            showShareSheet = true
                        } label: {
                            Label("PDF Olarak Paylaş", systemImage: "doc.fill")
                        }
                    } label: {
                        Image(systemName: "square.and.arrow.up")
                            .foregroundColor(.white)
                    }
                }
            }
        }
        .sheet(isPresented: $showShareSheet) {
            if let img = shareImage {
                ShareSheet(items: [img])
            } else if let data = pdfData {
                ShareSheet(items: [data])
            }
        }
        .sheet(item: $selectedLocation) { loc in
            LocationDetailSheet(location: loc)
        }
        .task {
            if let preloaded = preloadedData {
                videoData = VideoResponse(id: videoId, filename: "", status: "completed",
                                          duration: nil, aiResults: preloaded)
                isLoading = false
            } else {
                startElapsedTimer()
                await pollVideoStatus()
            }
        }
        .onDisappear { elapsedTimer?.invalidate() }
    }

    // MARK: - Analiz Yükleme Ekranı

    var analysisLoadingView: some View {
        VStack(spacing: 36) {
            Spacer()

            // Dairesel progress
            ZStack {
                // Arka plan halkası
                Circle()
                    .stroke(Color.white.opacity(0.08), lineWidth: 6)
                    .frame(width: 130, height: 130)

                // Gerçek ilerleme yayı
                Circle()
                    .trim(from: 0, to: CGFloat(progressPercent) / 100)
                    .stroke(
                        LinearGradient(colors: [.blue, .purple], startPoint: .leading, endPoint: .trailing),
                        style: StrokeStyle(lineWidth: 6, lineCap: .round)
                    )
                    .frame(width: 130, height: 130)
                    .rotationEffect(.degrees(-90))
                    .animation(.easeInOut(duration: 0.6), value: progressPercent)

                // İkon + yüzde
                VStack(spacing: 4) {
                    Image(systemName: currentStageInfo.icon)
                        .font(.system(size: 28))
                        .foregroundColor(.blue)
                        .id(progressStage)
                        .transition(.scale.combined(with: .opacity))
                        .animation(.spring(response: 0.4), value: progressStage)

                    Text("%\(progressPercent)")
                        .font(.system(size: 13, weight: .bold, design: .monospaced))
                        .foregroundColor(.white.opacity(0.6))
                }
            }

            // Aşama metni
            VStack(spacing: 6) {
                Text("AI Analiz Ediyor")
                    .font(.title2).fontWeight(.bold)
                    .foregroundColor(.white)

                Text(currentStageInfo.text)
                    .font(.subheadline)
                    .foregroundColor(.white.opacity(0.55))
                    .multilineTextAlignment(.center)
                    .id(progressStage)
                    .transition(.opacity)
                    .animation(.easeInOut(duration: 0.35), value: progressStage)
            }

            // Adım noktaları
            let orderedStages = ["metadata","frames","ai_parallel","ner","ner_ocr","geocoding","overpass","dedup","route","rag"]
            let currentIdx = orderedStages.firstIndex(of: progressStage) ?? 0
            HStack(spacing: 5) {
                ForEach(Array(orderedStages.enumerated()), id: \.element) { i, _ in
                    Circle()
                        .fill(i <= currentIdx ? Color.blue : Color.white.opacity(0.15))
                        .frame(width: i == currentIdx ? 10 : 6, height: i == currentIdx ? 10 : 6)
                        .animation(.spring(response: 0.3), value: progressStage)
                }
            }

            // Geçen süre
            Text("⏱ \(formattedElapsed())  ·  Bu işlem 1-3 dakika sürebilir")
                .font(.caption)
                .foregroundColor(.white.opacity(0.3))

            Spacer()
        }
        .padding(40)
    }

    func formattedElapsed() -> String {
        let m = elapsedSeconds / 60
        let s = elapsedSeconds % 60
        return m > 0 ? "\(m)d \(String(format: "%02d", s))s" : "\(s)s"
    }

    // MARK: - Hata

    func errorView(message: String) -> some View {
        VStack(spacing: 0) {
            Spacer()

            // İkon
            ZStack {
                Circle()
                    .fill(Color.red.opacity(0.12))
                    .frame(width: 110, height: 110)
                Circle()
                    .stroke(Color.red.opacity(0.25), lineWidth: 1)
                    .frame(width: 110, height: 110)
                Image(systemName: "exclamationmark.triangle.fill")
                    .font(.system(size: 44))
                    .foregroundStyle(
                        LinearGradient(colors: [.orange, .red], startPoint: .top, endPoint: .bottom)
                    )
            }

            Spacer().frame(height: 28)

            Text("İşlem Başarısız")
                .font(.title2).fontWeight(.bold)
                .foregroundColor(.white)

            Spacer().frame(height: 10)

            Text(friendlyError(message))
                .font(.subheadline)
                .foregroundColor(.white.opacity(0.55))
                .multilineTextAlignment(.center)
                .padding(.horizontal, 32)

            Spacer().frame(height: 36)

            // Tekrar dene
            Button {
                Task {
                    await MainActor.run {
                        errorMessage = nil
                        isLoading = true
                        progressPercent = 5
                        progressStage = "metadata"
                        elapsedSeconds = 0
                    }
                    startElapsedTimer()
                    await pollVideoStatus()
                }
            } label: {
                HStack(spacing: 8) {
                    Image(systemName: "arrow.clockwise")
                    Text("Tekrar Dene")
                        .fontWeight(.semibold)
                }
                .frame(maxWidth: .infinity)
                .padding(.vertical, 16)
                .background(Color.blue)
                .foregroundColor(.white)
                .cornerRadius(14)
                .padding(.horizontal, 40)
            }

            Spacer().frame(height: 16)

            // Geri dön
            Button("Ana Sayfaya Dön") {
                dismiss()
            }
            .font(.subheadline)
            .foregroundColor(.white.opacity(0.4))

            Spacer()
        }
        .padding()
    }

    func friendlyError(_ raw: String) -> String {
        if raw.contains("timeout") || raw.contains("timed out") {
            return "Video işleme zaman aşımına uğradı.\nDaha kısa bir video deneyin."
        }
        if raw.contains("failed") || raw.contains("başarısız") {
            return "Video işlenemedi.\nFarklı bir video dosyası deneyin."
        }
        if raw.contains("404") { return "Video bulunamadı." }
        if raw.contains("500") { return "Sunucu hatası. Lütfen daha sonra tekrar deneyin." }
        return "Beklenmedik bir hata oluştu.\nLütfen tekrar deneyin."
    }

    // MARK: - Sonuçlar

    @ViewBuilder
    func resultsContent(video: VideoResponse) -> some View {
        let ai = video.aiResults
        let locations   = ai?.nominatim?.deduplicatedLocations ?? []
        let nerLocs     = ai?.ner?.extractedLocations ?? []
        let ocrPois     = ai?.ocrPois ?? []
        let ocrTexts    = ai?.ocr?.extractedTexts ?? []
        let tips        = ai?.rag?.travelTips?.tips ?? []
        let summary     = ai?.rag?.travelTips?.summary
        let transcript  = ai?.audio?.transcription?.transcript
        let hasData     = !locations.isEmpty || !nerLocs.isEmpty || !ocrPois.isEmpty

        ScrollView {
            VStack(alignment: .leading, spacing: 14) {

                // ── Özet başlık banner ──
                summaryBanner(locations: locations, nerLocs: nerLocs, ocrCount: ocrPois.count)

                // ── Harita ──
                if !locations.isEmpty {
                    DarkCard(title: "🗺️ Rota Haritası") {
                        TripMapView(locations: locations)
                            .frame(height: 220)
                            .cornerRadius(12)
                            .overlay(
                                RoundedRectangle(cornerRadius: 12)
                                    .stroke(Color.white.opacity(0.08), lineWidth: 1)
                            )
                    }
                }

                // ── Gezilen Mekanlar ──
                if !locations.isEmpty {
                    DarkCard(title: "📍 Bulunan Mekanlar (\(locations.count))") {
                        VStack(alignment: .leading, spacing: 10) {
                            ForEach(Array(locations.enumerated()), id: \.element.originalName) { idx, loc in
                                LocationRow(index: idx + 1, location: loc)
                                    .contentShape(Rectangle())
                                    .onTapGesture { selectedLocation = loc }
                            }
                        }
                    }
                } else if !nerLocs.isEmpty {
                    DarkCard(title: "📍 Tespit Edilen Yerler") {
                        VStack(alignment: .leading, spacing: 8) {
                            ForEach(nerLocs, id: \.self) { loc in
                                HStack(spacing: 10) {
                                    Image(systemName: "location.circle.fill")
                                        .foregroundColor(.purple)
                                    Text(loc.capitalized)
                                        .foregroundColor(.white).font(.subheadline)
                                }
                            }
                        }
                    }
                }

                // ── OCR — Videoda Okunan İşletmeler ──
                let displayTexts = ocrPois.isEmpty ? ocrTexts : ocrPois
                // Haritada zaten pinlenen yerleri OCR listesinden çıkar
                let geocodedNames = Set(locations.map { $0.originalName.lowercased() })
                let ungeocoded = displayTexts.filter { !geocodedNames.contains($0.lowercased()) }

                if !ungeocoded.isEmpty {
                    DarkCard(title: "🏪 Haritada Konumu Bulunamayan İşletmeler") {
                        VStack(alignment: .leading, spacing: 8) {
                            ForEach(ungeocoded.prefix(20), id: \.self) { text in
                                HStack(spacing: 10) {
                                    Image(systemName: poiIcon(text))
                                        .font(.caption)
                                        .foregroundColor(.orange)
                                        .frame(width: 18)
                                    Text(text)
                                        .font(.subheadline)
                                        .foregroundColor(.white.opacity(0.85))
                                    Spacer()
                                    // Apple Maps arama butonu
                                    Button {
                                        let query = text.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? ""
                                        if let url = URL(string: "maps://?q=\(query)") {
                                            UIApplication.shared.open(url)
                                        }
                                    } label: {
                                        Image(systemName: "map")
                                            .font(.caption)
                                            .foregroundColor(.blue)
                                            .padding(6)
                                            .background(Color.blue.opacity(0.12))
                                            .cornerRadius(6)
                                    }
                                }
                                .padding(.horizontal, 4)
                            }
                            Text("Tıklayarak Apple Maps'te arayabilirsin")
                                .font(.caption2)
                                .foregroundColor(.white.opacity(0.3))
                                .padding(.top, 2)
                        }
                    }
                }

                // ── Ses Transkripsiyon ──
                if let t = transcript, !t.isEmpty {
                    DarkCard(title: "🎙️ Ses Transkripsiyonu") {
                        Text(t)
                            .font(.subheadline)
                            .foregroundColor(.white.opacity(0.75))
                            .lineSpacing(5)
                    }
                }

                // ── Seyahat İpuçları ──
                if !tips.isEmpty {
                    DarkCard(title: "💡 Seyahat İpuçları") {
                        VStack(alignment: .leading, spacing: 10) {
                            ForEach(tips, id: \.location) { tip in
                                HStack(alignment: .top, spacing: 12) {
                                    Image(systemName: "lightbulb.fill")
                                        .foregroundColor(.yellow).font(.caption)
                                        .padding(.top, 3)
                                    VStack(alignment: .leading, spacing: 3) {
                                        Text(tip.location)
                                            .font(.caption).fontWeight(.semibold)
                                            .foregroundColor(.orange)
                                        Text(tip.tip)
                                            .font(.caption)
                                            .foregroundColor(.white.opacity(0.7))
                                    }
                                }
                                .padding(10)
                                .background(Color.white.opacity(0.04))
                                .cornerRadius(10)
                            }
                        }
                    }
                }

                // ── Gezi Özeti ──
                if let s = summary, !s.isEmpty {
                    DarkCard(title: "📖 Gezi Özeti") {
                        Text(s)
                            .font(.subheadline)
                            .foregroundColor(.white.opacity(0.8))
                            .lineSpacing(5)
                    }
                }

                // ── Veri yok ──
                if !hasData {
                    DarkCard(title: "ℹ️ Bilgi") {
                        Text("Bu videodan lokasyon veya mekan bilgisi çıkarılamadı.\nTürkçe ses ya da yer yazısı içeren videolar deneyin.")
                            .font(.subheadline)
                            .foregroundColor(.white.opacity(0.7))
                            .lineSpacing(4)
                    }
                }

                // ── İstatistikler ──
                if let pt = ai?.processingTime {
                    DarkCard(title: "⚡ İşlem Bilgisi") {
                        HStack(spacing: 0) {
                            StatItem(value: "\(Int(pt))s",                    label: "Süre")
                            StatItem(value: "\(video.duration ?? 0)s",        label: "Video")
                            StatItem(value: "\(ai?.detections?.count ?? 0)",  label: "Nesne")
                            StatItem(value: "\(locations.count)",              label: "Mekan")
                        }
                    }
                }
            }
            .padding()
        }
    }

    // MARK: - Özet Banner

    @ViewBuilder
    func summaryBanner(locations: [EnrichedLocation], nerLocs: [String], ocrCount: Int) -> some View {
        let total = locations.count + (locations.isEmpty ? nerLocs.count : 0)
        HStack(spacing: 16) {
            VStack(alignment: .leading, spacing: 4) {
                Text(total > 0 ? "\(total) Mekan Bulundu" : "Analiz Tamamlandı")
                    .font(.title3).fontWeight(.bold).foregroundColor(.white)
                if let first = locations.first?.originalName.capitalized {
                    Text("İlk durak: \(first)")
                        .font(.caption).foregroundColor(.white.opacity(0.5))
                }
            }
            Spacer()
            if total > 0 {
                ZStack {
                    Circle().fill(Color.blue.opacity(0.2)).frame(width: 54, height: 54)
                    Text("\(total)")
                        .font(.title2).fontWeight(.black).foregroundColor(.blue)
                }
            }
        }
        .padding(16)
        .background(
            LinearGradient(colors: [Color.blue.opacity(0.15), Color.purple.opacity(0.1)],
                           startPoint: .leading, endPoint: .trailing)
        )
        .cornerRadius(16)
        .overlay(RoundedRectangle(cornerRadius: 16).stroke(Color.blue.opacity(0.2), lineWidth: 1))
    }

    // MARK: - POI İkon Yardımcısı

    func poiIcon(_ text: String) -> String {
        let t = text.lowercased()
        if t.contains("kafe") || t.contains("cafe") || t.contains("kahve") { return "cup.and.saucer.fill" }
        if t.contains("dürüm") || t.contains("kebap") || t.contains("lokant") || t.contains("restoran") { return "fork.knife" }
        if t.contains("fırın") || t.contains("pastane") || t.contains("börek") { return "birthday.cake.fill" }
        if t.contains("müze") || t.contains("han") || t.contains("saray") { return "building.columns.fill" }
        if t.contains("cami") || t.contains("türbe") || t.contains("kilise") { return "building.fill" }
        if t.contains("park") || t.contains("bahçe") { return "leaf.fill" }
        if t.contains("otel") || t.contains("pansiyon") { return "bed.double.fill" }
        return "storefront.fill"
    }

    // MARK: - Instagram Stories Paylaşım

    func shareToInstagramStories(image: UIImage) {
        let storiesURL = URL(string: "instagram-stories://share?source_application=com.suleymanssardogan.TripClipAI")!

        guard UIApplication.shared.canOpenURL(storiesURL) else {
            // Instagram kurulu değil → sistem share sheet'e düş
            shareImage     = image
            showShareSheet = true
            return
        }

        guard let imageData = image.pngData() else { return }

        // Görseli pasteboard'a koy, Instagram oradan okur
        UIPasteboard.general.setItems(
            [[UTType.png.identifier: imageData]],
            options: [.expirationDate: Date().addingTimeInterval(300)] // 5 dk geçerli
        )

        UIApplication.shared.open(storiesURL)
    }

    // MARK: - Polling

    func startElapsedTimer() {
        elapsedSeconds = 0
        elapsedTimer?.invalidate()
        elapsedTimer = Timer.scheduledTimer(withTimeInterval: 1, repeats: true) { _ in
            elapsedSeconds += 1
        }
    }

    func pollVideoStatus() async {
        isLoading = true
        // Her 3 saniyede video durumunu kontrol et; her 2 saniyede progress'i güncelle
        var pollCount = 0
        let maxPolls = 200 // ~10 dakika
        while pollCount < maxPolls {
            pollCount += 1

            // Progress güncelle (her iterasyonda — sunucudan gerçek değer)
            if let prog = try? await APIService.shared.getVideoProgress(id: videoId) {
                await MainActor.run {
                    withAnimation {
                        if let s = prog.stage   { progressStage   = s }
                        if let p = prog.percent { progressPercent = p }
                    }
                }
            }

            // Video durumunu kontrol et
            do {
                let video = try await APIService.shared.getVideoStatus(id: videoId)
                if video.status == "completed" {
                    PersistenceService.shared.saveVideoResult(video)
                    elapsedTimer?.invalidate()
                    await MainActor.run {
                        withAnimation { progressPercent = 100 }
                        videoData = video
                        isLoading = false
                    }
                    return
                } else if video.status == "failed" {
                    elapsedTimer?.invalidate()
                    await MainActor.run { errorMessage = "Video işleme başarısız oldu."; isLoading = false }
                    return
                }
            } catch {
                elapsedTimer?.invalidate()
                await MainActor.run { errorMessage = error.localizedDescription; isLoading = false }
                return
            }

            try? await Task.sleep(nanoseconds: 3_000_000_000) // 3s
        }
        elapsedTimer?.invalidate()
        await MainActor.run { errorMessage = "Zaman aşımı — lütfen tekrar deneyin."; isLoading = false }
    }
}

// MARK: - Konum Satırı

struct LocationRow: View {
    let index: Int
    let location: EnrichedLocation

    var body: some View {
        HStack(spacing: 12) {
            // Sıra numarası
            ZStack {
                Circle().fill(Color.blue.opacity(0.15)).frame(width: 32, height: 32)
                Text("\(index)").font(.caption).fontWeight(.bold).foregroundColor(.blue)
            }

            VStack(alignment: .leading, spacing: 3) {
                Text(location.originalName.capitalized)
                    .font(.subheadline).fontWeight(.semibold).foregroundColor(.white)
                if let name = location.placeData?.name {
                    Text(name)
                        .font(.caption).foregroundColor(.white.opacity(0.45)).lineLimit(1)
                }
            }

            Spacer()

            // Kategori rozeti
            if let cat = location.placeData?.category {
                Text(categoryEmoji(cat) + " " + cat)
                    .font(.caption2).fontWeight(.medium)
                    .foregroundColor(.orange.opacity(0.9))
                    .padding(.horizontal, 8).padding(.vertical, 4)
                    .background(Color.orange.opacity(0.1))
                    .cornerRadius(8)
            }

            Image(systemName: "chevron.right")
                .font(.caption2).foregroundColor(.white.opacity(0.3))
        }
        .padding(10)
        .background(Color.white.opacity(0.04))
        .cornerRadius(12)
    }

    func categoryEmoji(_ cat: String) -> String {
        let map: [String: String] = [
            "Müze": "🏛️", "Kale": "🏰", "Tarihi Alan": "🏺",
            "Arkeolojik Alan": "⛏️", "Cami": "🕌", "Kilise": "⛪",
            "Anıt": "🗿", "Köprü": "🌉", "Kafe": "☕",
            "Restoran": "🍽️", "Bar": "🍺", "Yemek": "🥙",
            "Park": "🌳", "Doğa Alanı": "🌿", "Plaj": "🏖️",
            "Şelale": "💧", "Zirve": "⛰️", "Manzara Noktası": "👁️",
            "Galeri": "🖼️", "Tiyatro": "🎭", "Sinema": "🎬",
            "Konaklama": "🏨", "Turistik Alan": "📸",
            "İbadet Yeri": "🙏", "Şehir": "🏙️", "İlçe": "🏘️",
            "Köy": "🌾", "Mekan": "📍",
        ]
        return map[cat] ?? "📍"
    }
}

// MARK: - Konum Detay Sheet

struct LocationDetailSheet: View {
    let location: EnrichedLocation
    @Environment(\.dismiss) var dismiss

    private var hasCoords: Bool {
        location.placeData?.location?.lat != nil
    }

    var body: some View {
        NavigationStack {
            ZStack {
                Color(hex: "0A0E1A").ignoresSafeArea()
                ScrollView {
                    VStack(alignment: .leading, spacing: 0) {

                        // ── Mini Harita ─────────────────────────────────
                        if let lat = location.placeData?.location?.lat,
                           let lng = location.placeData?.location?.lng {
                            let coord = CLLocationCoordinate2D(latitude: lat, longitude: lng)
                            DetailMapView(coordinate: coord, title: location.originalName.capitalized)
                                .frame(height: 220)
                                .ignoresSafeArea(edges: .horizontal)
                        } else {
                            // Koordinat yok — placeholder
                            ZStack {
                                Color.white.opacity(0.04)
                                VStack(spacing: 8) {
                                    Image(systemName: "map.fill")
                                        .font(.system(size: 36))
                                        .foregroundColor(.white.opacity(0.2))
                                    Text("Konum bulunamadı")
                                        .font(.caption)
                                        .foregroundColor(.white.opacity(0.3))
                                }
                            }
                            .frame(height: 120)
                        }

                        VStack(alignment: .leading, spacing: 20) {

                            // ── Başlık Bilgi Kartı ───────────────────────
                            VStack(alignment: .leading, spacing: 10) {
                                // Kategori rozeti
                                if let cat = location.placeData?.category {
                                    Text(categoryEmoji(cat) + "  " + cat)
                                        .font(.caption).fontWeight(.semibold)
                                        .foregroundColor(.orange)
                                        .padding(.horizontal, 10).padding(.vertical, 5)
                                        .background(Color.orange.opacity(0.12))
                                        .cornerRadius(20)
                                }

                                Text(location.originalName.capitalized)
                                    .font(.title2).fontWeight(.bold).foregroundColor(.white)

                                if let name = location.placeData?.name,
                                   name.lowercased() != location.originalName.lowercased() {
                                    Text(name)
                                        .font(.subheadline).foregroundColor(.white.opacity(0.45))
                                }
                            }

                            // ── Koordinat bilgisi ────────────────────────
                            if let lat = location.placeData?.location?.lat,
                               let lng = location.placeData?.location?.lng {
                                HStack(spacing: 20) {
                                    DetailInfoTile(icon: "location.fill", label: "Enlem",  value: String(format: "%.4f°", lat), color: .blue)
                                    DetailInfoTile(icon: "location.fill", label: "Boylam", value: String(format: "%.4f°", lng), color: .purple)
                                }
                            }

                            // ── Önem skoru ──────────────────────────────
                            if let imp = location.placeData?.importance {
                                let pct = min(Int(imp * 100), 100)
                                VStack(alignment: .leading, spacing: 6) {
                                    HStack {
                                        Image(systemName: "star.fill").font(.caption).foregroundColor(.yellow)
                                        Text("Popülerlik")
                                            .font(.caption).foregroundColor(.white.opacity(0.5))
                                        Spacer()
                                        Text("%\(pct)")
                                            .font(.caption).fontWeight(.bold).foregroundColor(.white)
                                    }
                                    GeometryReader { geo in
                                        ZStack(alignment: .leading) {
                                            RoundedRectangle(cornerRadius: 4)
                                                .fill(Color.white.opacity(0.08))
                                            RoundedRectangle(cornerRadius: 4)
                                                .fill(LinearGradient(colors: [.yellow, .orange],
                                                                     startPoint: .leading, endPoint: .trailing))
                                                .frame(width: geo.size.width * CGFloat(pct) / 100)
                                        }
                                    }
                                    .frame(height: 6)
                                }
                                .padding(14)
                                .background(Color.white.opacity(0.05))
                                .cornerRadius(12)
                            }

                            // ── Harita Butonları ─────────────────────────
                            if let lat = location.placeData?.location?.lat,
                               let lng = location.placeData?.location?.lng {
                                VStack(spacing: 10) {
                                    Button {
                                        let url = URL(string: "maps://?daddr=\(lat),\(lng)&dirflg=d")!
                                        UIApplication.shared.open(url)
                                    } label: {
                                        HStack {
                                            Image(systemName: "map.fill")
                                            Text("Apple Maps'te Yol Tarifi Al")
                                                .fontWeight(.semibold)
                                        }
                                        .frame(maxWidth: .infinity)
                                        .padding(.vertical, 15)
                                        .background(Color.blue)
                                        .foregroundColor(.white)
                                        .cornerRadius(14)
                                    }

                                    Button {
                                        let encoded = location.originalName
                                            .addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? ""
                                        let url = URL(string: "https://www.google.com/maps/search/?api=1&query=\(encoded)&center=\(lat),\(lng)")!
                                        UIApplication.shared.open(url)
                                    } label: {
                                        HStack {
                                            Image(systemName: "globe")
                                            Text("Google Maps'te Ara")
                                                .fontWeight(.semibold)
                                        }
                                        .frame(maxWidth: .infinity)
                                        .padding(.vertical, 15)
                                        .background(Color.white.opacity(0.07))
                                        .foregroundColor(.white)
                                        .cornerRadius(14)
                                        .overlay(RoundedRectangle(cornerRadius: 14)
                                            .stroke(Color.white.opacity(0.1), lineWidth: 1))
                                    }
                                }
                            }
                        }
                        .padding(20)
                    }
                }
            }
            .navigationTitle(location.originalName.capitalized)
            .navigationBarTitleDisplayMode(.inline)
            .toolbarColorScheme(.dark, for: .navigationBar)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Kapat") { dismiss() }.foregroundColor(.white)
                }
            }
        }
    }

    func categoryEmoji(_ cat: String) -> String {
        let map: [String: String] = [
            "Müze":"🏛️","Kale":"🏰","Tarihi Alan":"🏺","Cami":"🕌",
            "Anıt":"🗿","Köprü":"🌉","Kafe":"☕","Restoran":"🍽️",
            "Park":"🌳","Plaj":"🏖️","Şelale":"💧","Zirve":"⛰️",
            "Turistik Alan":"📸","Konaklama":"🏨","Şehir":"🏙️","Mekan":"📍",
        ]
        return map[cat] ?? "📍"
    }
}

// MARK: - Yardımcı: Detay Bilgi Kartı

struct DetailInfoTile: View {
    let icon: String
    let label: String
    let value: String
    let color: Color

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack(spacing: 4) {
                Image(systemName: icon).font(.caption2).foregroundColor(color)
                Text(label).font(.caption2).foregroundColor(.white.opacity(0.4))
            }
            Text(value)
                .font(.system(.caption, design: .monospaced))
                .fontWeight(.medium)
                .foregroundColor(.white)
        }
        .padding(12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color.white.opacity(0.05))
        .cornerRadius(10)
    }
}

// MARK: - Detay Harita (UIKit wrapper — koordinat pin'i)

struct DetailMapView: UIViewRepresentable {
    let coordinate: CLLocationCoordinate2D
    let title: String

    func makeUIView(context: Context) -> MKMapView {
        let map = MKMapView()
        map.mapType = .standard
        map.isScrollEnabled = false
        map.isZoomEnabled = false
        map.isUserInteractionEnabled = false
        map.layer.cornerRadius = 0
        return map
    }

    func updateUIView(_ mapView: MKMapView, context: Context) {
        mapView.removeAnnotations(mapView.annotations)
        let pin = MKPointAnnotation()
        pin.coordinate = coordinate
        pin.title = title
        mapView.addAnnotation(pin)
        mapView.setRegion(
            MKCoordinateRegion(center: coordinate,
                               latitudinalMeters: 1500,
                               longitudinalMeters: 1500),
            animated: false
        )
    }
}

// MARK: - Rota Haritası (numaralı pinler + çizgi)

struct TripMapView: UIViewRepresentable {
    let locations: [EnrichedLocation]

    func makeCoordinator() -> Coordinator { Coordinator() }

    func makeUIView(context: Context) -> MKMapView {
        let map = MKMapView()
        map.mapType = .standard
        map.showsUserLocation = false
        map.delegate = context.coordinator
        return map
    }

    func updateUIView(_ mapView: MKMapView, context: Context) {
        mapView.removeAnnotations(mapView.annotations)
        mapView.removeOverlays(mapView.overlays)

        var coords: [CLLocationCoordinate2D] = []
        for (i, loc) in locations.enumerated() {
            guard let lat = loc.placeData?.location?.lat,
                  let lng = loc.placeData?.location?.lng else { continue }
            let c = CLLocationCoordinate2D(latitude: lat, longitude: lng)
            coords.append(c)
            let pin = NumberedAnnotation(index: i + 1)
            pin.coordinate = c
            pin.title = "\(i + 1). \(loc.originalName.capitalized)"
            mapView.addAnnotation(pin)
        }

        if coords.count > 1 {
            let polyline = MKPolyline(coordinates: coords, count: coords.count)
            mapView.addOverlay(polyline)
        }

        if !coords.isEmpty {
            let rect = coords.reduce(MKMapRect.null) { rect, c in
                let pt = MKMapPoint(c)
                return rect.union(MKMapRect(x: pt.x, y: pt.y, width: 0, height: 0))
            }
            mapView.setVisibleMapRect(
                rect,
                edgePadding: UIEdgeInsets(top: 44, left: 44, bottom: 44, right: 44),
                animated: false
            )
        }
    }

    // MARK: Coordinator (delegate)
    class Coordinator: NSObject, MKMapViewDelegate {
        func mapView(_ mapView: MKMapView, rendererFor overlay: MKOverlay) -> MKOverlayRenderer {
            if let polyline = overlay as? MKPolyline {
                let r = MKPolylineRenderer(polyline: polyline)
                r.strokeColor = UIColor.systemBlue.withAlphaComponent(0.7)
                r.lineWidth = 2.5
                r.lineDashPattern = [6, 4]
                return r
            }
            return MKOverlayRenderer(overlay: overlay)
        }

        func mapView(_ mapView: MKMapView, viewFor annotation: MKAnnotation) -> MKAnnotationView? {
            guard let numbered = annotation as? NumberedAnnotation else { return nil }
            let id = "numbered"
            let view = mapView.dequeueReusableAnnotationView(withIdentifier: id)
                ?? MKAnnotationView(annotation: annotation, reuseIdentifier: id)
            view.annotation = annotation

            // Numaralı daire çiz
            let size: CGFloat = 26
            let label = UILabel(frame: CGRect(x: 0, y: 0, width: size, height: size))
            label.text = "\(numbered.index)"
            label.textAlignment = .center
            label.font = .boldSystemFont(ofSize: 11)
            label.textColor = .white
            label.backgroundColor = UIColor.systemBlue
            label.layer.cornerRadius = size / 2
            label.layer.masksToBounds = true

            UIGraphicsBeginImageContextWithOptions(CGSize(width: size, height: size), false, 0)
            label.layer.render(in: UIGraphicsGetCurrentContext()!)
            view.image = UIGraphicsGetImageFromCurrentImageContext()
            UIGraphicsEndImageContext()

            view.centerOffset = CGPoint(x: 0, y: -size / 2)
            view.canShowCallout = true
            return view
        }
    }
}

class NumberedAnnotation: MKPointAnnotation {
    let index: Int
    init(index: Int) { self.index = index; super.init() }
    required init?(coder: NSCoder) { fatalError() }
}

// MARK: - FlowLayout

struct FlowLayout: Layout {
    var spacing: CGFloat = 8
    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        let rows = computeRows(proposal: proposal, subviews: subviews)
        let height = rows.map { $0.map { $0.sizeThatFits(.unspecified).height }.max() ?? 0 }.reduce(0, +)
            + CGFloat(max(rows.count - 1, 0)) * spacing
        return CGSize(width: proposal.width ?? 0, height: height)
    }
    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        var y = bounds.minY
        for row in computeRows(proposal: proposal, subviews: subviews) {
            var x = bounds.minX
            let h = row.map { $0.sizeThatFits(.unspecified).height }.max() ?? 0
            for view in row {
                let s = view.sizeThatFits(.unspecified)
                view.place(at: CGPoint(x: x, y: y), proposal: ProposedViewSize(s))
                x += s.width + spacing
            }
            y += h + spacing
        }
    }
    private func computeRows(proposal: ProposedViewSize, subviews: Subviews) -> [[LayoutSubview]] {
        var rows: [[LayoutSubview]] = [[]]
        var x: CGFloat = 0
        let maxW = proposal.width ?? 300
        for view in subviews {
            let w = view.sizeThatFits(.unspecified).width
            if x + w > maxW && !rows[rows.count-1].isEmpty { rows.append([]); x = 0 }
            rows[rows.count-1].append(view)
            x += w + spacing
        }
        return rows
    }
}

// MARK: - DarkCard

struct DarkCard<Content: View>: View {
    let title: String
    @ViewBuilder let content: Content
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text(title).font(.headline).foregroundColor(.white)
            content
        }
        .padding(16)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color.white.opacity(0.06))
        .cornerRadius(16)
        .overlay(RoundedRectangle(cornerRadius: 16).stroke(Color.white.opacity(0.08), lineWidth: 1))
    }
}

// MARK: - StatItem

struct StatItem: View {
    let value: String
    let label: String
    var body: some View {
        VStack(spacing: 4) {
            Text(value).font(.title3).fontWeight(.bold).foregroundColor(.white)
            Text(label).font(.caption).foregroundColor(.white.opacity(0.45))
        }
        .frame(maxWidth: .infinity)
    }
}

// MARK: - ShareSheet

import UIKit
struct ShareSheet: UIViewControllerRepresentable {
    let items: [Any]
    func makeUIViewController(context: Context) -> UIActivityViewController {
        UIActivityViewController(activityItems: items, applicationActivities: nil)
    }
    func updateUIViewController(_ vc: UIActivityViewController, context: Context) {}
}

// MARK: - EnrichedLocation: Identifiable

extension EnrichedLocation: Identifiable {
    public var id: String { originalName }
}

// MARK: - Preview

#Preview {
    NavigationStack { ResultsView(videoId: 1) }
}
