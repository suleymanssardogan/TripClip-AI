import SwiftUI

struct ResultsView: View {
    let videoId: Int
    @State private var videoData: VideoResponse?
    @State private var isLoading = true
    @State private var errorMessage: String?
    
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                
                if isLoading {
                    VStack(spacing: 16) {
                        ProgressView()
                            .scaleEffect(1.5)
                        Text("AI analiz ediyor...")
                            .font(.subheadline)
                            .foregroundColor(.secondary)
                    }
                    .frame(maxWidth: .infinity)
                    .padding(.top, 100)
                    
                } else if let video = videoData {
                    
                    // Lokasyonlar
                    if let locations = video.aiResults?.ner?.extractedLocations, !locations.isEmpty {
                        SectionCard(title: "📍 Tespit Edilen Yerler") {
                            ForEach(locations, id: \.self) { location in
                                HStack {
                                    Image(systemName: "mappin")
                                        .foregroundColor(.blue)
                                    Text(location)
                                }
                            }
                        }
                    }
                    
                    // Travel Tips
                    if let tips = video.aiResults?.rag?.travelTips?.tips, !tips.isEmpty {
                        SectionCard(title: "💡 Seyahat İpuçları") {
                            ForEach(tips, id: \.location) { tip in
                                VStack(alignment: .leading, spacing: 8) {
                                    Text(tip.location)
                                        .font(.headline)
                                    Text(tip.tip)
                                        .font(.subheadline)
                                        .foregroundColor(.secondary)
                                }
                                .padding(.bottom, 8)
                            }
                        }
                    }
                    
                    // Özet
                    if let summary = video.aiResults?.rag?.travelTips?.summary {
                        SectionCard(title: "📝 Gezi Özeti") {
                            Text(summary)
                                .font(.subheadline)
                                .foregroundColor(.secondary)
                        }
                    }
                    
                } else if let error = errorMessage {
                    Text(error)
                        .foregroundColor(.red)
                        .padding()
                }
            }
            .padding()
        }
        .navigationTitle("Gezi Planın")
        .navigationBarTitleDisplayMode(.large)
        .task {
            await pollVideoStatus()
        }
    }
    
    func pollVideoStatus() async {
        for _ in 0..<120 {
            do {
                let video = try await APIService.shared.getVideoStatus(id: videoId)
                
                if video.status == "completed" {
                    await MainActor.run {
                        videoData = video
                        isLoading = false
                    }
                    return
                } else if video.status == "failed" {
                    await MainActor.run {
                        errorMessage = "Video işleme başarısız"
                        isLoading = false
                    }
                    return
                }
                
                try await Task.sleep(nanoseconds: 5_000_000_000) // 5 saniye
            } catch {
                await MainActor.run {
                    errorMessage = error.localizedDescription
                    isLoading = false
                }
                return
            }
        }
        
        await MainActor.run {
            errorMessage = "Zaman aşımı"
            isLoading = false
        }
    }
}

// Yardımcı kart componenti
struct SectionCard<Content: View>: View {
    let title: String
    @ViewBuilder let content: Content
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text(title)
                .font(.headline)
            content
        }
        .padding()
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color(.systemGray6))
        .cornerRadius(12)
    }
}

#Preview {
    NavigationStack {
        ResultsView(videoId: 1)
    }
}

