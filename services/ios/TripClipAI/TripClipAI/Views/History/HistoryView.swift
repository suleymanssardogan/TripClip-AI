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

    var body: some View {
        HStack(spacing: 12) {
            ZStack {
                RoundedRectangle(cornerRadius: 10)
                    .fill(Color.blue.opacity(0.15))
                    .frame(width: 44, height: 44)
                Image(systemName: "map.fill")
                    .foregroundColor(.blue)
            }
            VStack(alignment: .leading, spacing: 4) {
                Text(video.filename ?? "Video")
                    .font(.subheadline)
                    .fontWeight(.medium)
                    .foregroundColor(.white)
                    .lineLimit(1)
                if let date = video.savedAt {
                    Text(date, style: .relative)
                        .font(.caption)
                        .foregroundColor(.white.opacity(0.5))
                }
            }
            Spacer()
        }
        .padding(.vertical, 4)
    }
}

struct OfflineResultsView: View {
    let video: SavedVideo

    var body: some View {
        if let results = video.decodedAIResults {
            ResultsView(videoId: Int(video.videoId), preloadedData: results)
        } else {
            Text("Veri yüklenemedi").foregroundColor(.white)
        }
    }
}
