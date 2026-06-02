import SwiftUI
import CoreData

struct HistoryView: View {
    @FetchRequest(
        entity: SavedVideo.entity(),
        sortDescriptors: [NSSortDescriptor(keyPath: \SavedVideo.savedAt, ascending: false)]
    ) private var savedVideos: FetchedResults<SavedVideo>

    @Environment(\.managedObjectContext) private var context

    var body: some View {
        ZStack {
            LinearGradient(
                colors: [Color(hex: "0A0E27"), Color(hex: "1a1a4e"), Color(hex: "0d2137")],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )
            .ignoresSafeArea()

            if savedVideos.isEmpty {
                VStack(spacing: 16) {
                    Image(systemName: "clock.arrow.trianglehead.counterclockwise.rotate.90")
                        .font(.system(size: 48))
                        .foregroundColor(.white.opacity(0.3))
                    Text("Henüz kaydedilmiş gezi yok")
                        .foregroundColor(.white.opacity(0.5))
                }
            } else {
                List {
                    ForEach(savedVideos, id: \.videoId) { video in
                        NavigationLink(destination: OfflineResultsView(video: video)) {
                            VideoHistoryRow(video: video)
                        }
                        .listRowBackground(Color.white.opacity(0.05))
                    }
                    .onDelete { indexSet in
                        indexSet.forEach { PersistenceService.shared.delete(savedVideos[$0]) }
                    }
                }
                .listStyle(.plain)
                .scrollContentBackground(.hidden)
            }
        }
        .navigationTitle("Geçmiş Geziler")
        .navigationBarTitleDisplayMode(.large)
        .toolbarColorScheme(.dark, for: .navigationBar)
    }
}

struct VideoHistoryRow: View {
    let video: SavedVideo

    /// Kayıtlı VideoResponse'tan lokasyonları çıkar (yeni format) → fallback eski format
    private var locations: [EnrichedLocation] {
        if let v = video.decodedVideoResponse {
            return v.enrichedLocations
        }
        return video.decodedAIResults?.nominatim?.deduplicatedLocations ?? []
    }

    /// Akıllı başlık üret
    /// 1) Lokasyon varsa → "Antalya Gezisi" (ilk yer ismi)
    /// 2) Yoksa → dosya adı (UUID)
    private var smartTitle: String {
        if let first = locations.first?.originalName, !first.isEmpty {
            return "\(first.capitalized) Gezisi"
        }
        return video.filename ?? "Video"
    }

    /// İkinci satır için lokasyon önizlemesi
    private var subtitle: String {
        if locations.count >= 2 {
            let names = locations.prefix(3).map { $0.originalName.capitalized }
            return names.joined(separator: " · ")
        }
        return "\(locations.count) mekan"
    }

    var body: some View {
        HStack(spacing: 12) {
            // Sol ikon — mekan sayısı rozetli
            ZStack {
                RoundedRectangle(cornerRadius: 12)
                    .fill(LinearGradient(
                        colors: [Color.blue.opacity(0.25), Color.purple.opacity(0.18)],
                        startPoint: .topLeading, endPoint: .bottomTrailing
                    ))
                    .frame(width: 50, height: 50)
                if locations.isEmpty {
                    Image(systemName: "map.fill")
                        .font(.system(size: 20))
                        .foregroundColor(.blue)
                } else {
                    VStack(spacing: 0) {
                        Text("\(locations.count)")
                            .font(.system(size: 18, weight: .bold, design: .rounded))
                            .foregroundColor(.white)
                        Text("yer")
                            .font(.system(size: 9, weight: .medium))
                            .foregroundColor(.white.opacity(0.6))
                    }
                }
            }

            VStack(alignment: .leading, spacing: 3) {
                Text(smartTitle)
                    .font(.subheadline)
                    .fontWeight(.semibold)
                    .foregroundColor(.white)
                    .lineLimit(1)

                if !locations.isEmpty {
                    Text(subtitle)
                        .font(.caption2)
                        .foregroundColor(.white.opacity(0.55))
                        .lineLimit(1)
                }

                if let date = video.savedAt {
                    HStack(spacing: 4) {
                        Image(systemName: "clock")
                            .font(.system(size: 9))
                        Text(date, style: .relative)
                            .font(.caption2)
                    }
                    .foregroundColor(.white.opacity(0.4))
                }
            }
            Spacer()

            // Sağ ok
            Image(systemName: "chevron.right")
                .font(.caption.weight(.semibold))
                .foregroundColor(.white.opacity(0.3))
        }
        .padding(.vertical, 6)
    }
}

struct OfflineResultsView: View {
    let video: SavedVideo

    var body: some View {
        // ResultsView her zaman fresh fetch yapar (videoId üzerinden);
        // bu yüzden cache içeriği değil id yeterli — internet yoksa
        // preloadedData ile fallback gösteririz.
        ResultsView(
            videoId: Int(video.videoId),
            preloadedData: video.decodedVideoResponse?.aiResults ?? video.decodedAIResults
        )
    }
}
