import SwiftUI
import PhotosUI

struct HomeView: View {
    @EnvironmentObject private var auth: AuthService

    // Upload flow
    @State private var selectedItem: PhotosPickerItem?
    @State private var isUploading      = false
    @State private var videoId: Int?
    @State private var errorMessage: String?
    @State private var navigateToResults = false
    @State private var uploadProgress: CGFloat = 0.0
    @State private var uploadStepText    = "Video yükleniyor..."
    @State private var uploadStepSubtext = "Lütfen bekleyin"
    @State private var uploadStepIcon    = "video.fill"

    // Logo
    @State private var animateLogo = false

    // Son geziler
    @State private var recentTrips: [SavedVideo]   = []
    @State private var selectedSavedVideo: SavedVideo? = nil
    @State private var navigateToOffline = false

    var body: some View {
        ZStack {
            LinearGradient(
                colors: [Color(hex: "0A0E27"), Color(hex: "1a1a4e"), Color(hex: "0d2137")],
                startPoint: .topLeading, endPoint: .bottomTrailing
            )
            .ignoresSafeArea()

            VStack(spacing: 0) {
                Spacer()

                // ── Logo ──
                VStack(spacing: 16) {
                    ZStack {
                        Circle().fill(Color.blue.opacity(0.08)).frame(width: 160, height: 160)
                        Circle().fill(Color.blue.opacity(0.15)).frame(width: 120, height: 120)
                        Image(systemName: "mappin.and.ellipse")
                            .font(.system(size: 56, weight: .light))
                            .foregroundStyle(
                                LinearGradient(colors: [.white, .blue], startPoint: .top, endPoint: .bottom)
                            )
                    }
                    .scaleEffect(animateLogo ? 1.05 : 1.0)
                    .animation(.easeInOut(duration: 2).repeatForever(autoreverses: true), value: animateLogo)

                    Text("TripClip AI")
                        .font(.system(size: 36, weight: .bold, design: .rounded))
                        .foregroundColor(.white)

                    Text("Gezi videolarından\notomatik seyahat planı")
                        .font(.subheadline)
                        .foregroundColor(.white.opacity(0.6))
                        .multilineTextAlignment(.center)
                }

                Spacer()

                // ── Nasıl çalışır ──
                HStack(spacing: 24) {
                    StepView(icon: "video.fill",  text: "Video\nSeç",  color: .blue)
                    Image(systemName: "arrow.right").foregroundColor(.white.opacity(0.3))
                    StepView(icon: "cpu.fill",    text: "AI\nAnaliz", color: .purple)
                    Image(systemName: "arrow.right").foregroundColor(.white.opacity(0.3))
                    StepView(icon: "map.fill",    text: "Plan\nAl",   color: .green)
                }
                .padding(.bottom, 40)

                // ── Upload / Loading ──
                if isUploading {
                    VStack(spacing: 20) {
                        ZStack {
                            Circle()
                                .stroke(Color.white.opacity(0.1), lineWidth: 4)
                                .frame(width: 80, height: 80)
                            Circle()
                                .trim(from: 0, to: uploadProgress)
                                .stroke(
                                    LinearGradient(colors: [.blue, .purple], startPoint: .leading, endPoint: .trailing),
                                    style: StrokeStyle(lineWidth: 4, lineCap: .round)
                                )
                                .frame(width: 80, height: 80)
                                .rotationEffect(.degrees(-90))
                                .animation(.easeInOut(duration: 0.5), value: uploadProgress)

                            Image(systemName: uploadStepIcon)
                                .font(.title2)
                                .foregroundColor(.white)
                        }

                        Text(uploadStepText)
                            .font(.headline).foregroundColor(.white)
                        Text(uploadStepSubtext)
                            .font(.caption).foregroundColor(.white.opacity(0.5))
                            .multilineTextAlignment(.center)
                    }
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 20)
                } else {
                    PhotosPicker(selection: $selectedItem, matching: .videos) {
                        HStack(spacing: 12) {
                            Image(systemName: "video.badge.plus").font(.headline)
                            Text("Video Seç ve Planla").font(.headline).fontWeight(.semibold)
                        }
                        .foregroundColor(.white)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 18)
                        .background(
                            LinearGradient(colors: [.blue, Color(hex: "4f46e5")], startPoint: .leading, endPoint: .trailing)
                        )
                        .cornerRadius(16)
                        .shadow(color: .blue.opacity(0.4), radius: 12, y: 6)
                    }
                    .padding(.horizontal, 24)
                }

                // Hata mesajı
                if let error = errorMessage {
                    Text(error)
                        .foregroundColor(.red.opacity(0.8))
                        .font(.caption)
                        .padding(.horizontal, 24)
                        .padding(.top, 8)
                        .multilineTextAlignment(.center)
                }

                // ── Son Geziler ──
                if !recentTrips.isEmpty && !isUploading {
                    VStack(alignment: .leading, spacing: 12) {
                        Text("Son Geziler")
                            .font(.caption)
                            .fontWeight(.semibold)
                            .foregroundColor(.white.opacity(0.45))
                            .padding(.horizontal, 28)

                        ScrollView(.horizontal, showsIndicators: false) {
                            HStack(spacing: 12) {
                                ForEach(recentTrips.prefix(3), id: \.videoId) { trip in
                                    Button {
                                        selectedSavedVideo = trip
                                        navigateToOffline   = true
                                    } label: {
                                        RecentTripCard(video: trip)
                                    }
                                }
                            }
                            .padding(.horizontal, 24)
                        }
                    }
                    .padding(.top, 28)
                }

                Spacer().frame(height: 40)
            }
        }
        .toolbar {
            ToolbarItem(placement: .navigationBarLeading) {
                Button { auth.logout() } label: {
                    Image(systemName: "rectangle.portrait.and.arrow.right")
                        .foregroundColor(.white.opacity(0.7))
                }
            }
            ToolbarItem(placement: .navigationBarTrailing) {
                NavigationLink(destination:
                    HistoryView()
                        .environment(\.managedObjectContext, PersistenceService.shared.context)
                ) {
                    Image(systemName: "clock.arrow.trianglehead.counterclockwise.rotate.90")
                        .foregroundColor(.white)
                }
            }
        }
        .onAppear {
            animateLogo = true
            recentTrips = PersistenceService.shared.fetchAll()
        }
        .onChange(of: selectedItem) { _, newItem in
            guard let item = newItem else { return }
            Task { await uploadVideo(item: item) }
        }
        .navigationDestination(isPresented: $navigateToResults) {
            if let id = videoId { ResultsView(videoId: id) }
        }
        .navigationDestination(isPresented: $navigateToOffline) {
            if let video = selectedSavedVideo {
                OfflineResultsView(video: video)
                    .environment(\.managedObjectContext, PersistenceService.shared.context)
            }
        }
    }

    // MARK: - Upload

    func uploadVideo(item: PhotosPickerItem) async {
        isUploading   = true
        errorMessage  = nil

        await MainActor.run {
            uploadProgress   = 0.15
            uploadStepIcon   = "doc.fill"
            uploadStepText   = "Video hazırlanıyor..."
            uploadStepSubtext = "Dosya okunuyor"
        }

        do {
            guard let data = try await item.loadTransferable(type: Data.self) else {
                throw URLError(.cannotDecodeContentData)
            }

            let sizeMB = String(format: "%.1f", Double(data.count) / 1_048_576)
            let tempURL = FileManager.default.temporaryDirectory
                .appendingPathComponent(UUID().uuidString + ".mp4")
            try data.write(to: tempURL)

            await MainActor.run {
                uploadProgress    = 0.45
                uploadStepIcon    = "icloud.and.arrow.up"
                uploadStepText    = "Sunucuya yükleniyor..."
                uploadStepSubtext = "\(sizeMB) MB gönderiliyor"
            }

            let id = try await APIService.shared.uploadVideo(fileURL: tempURL)
            try? FileManager.default.removeItem(at: tempURL) // 🧹 temp dosyayı temizle

            await MainActor.run {
                uploadProgress    = 0.9
                uploadStepIcon    = "cpu.fill"
                uploadStepText    = "AI analiz başlıyor..."
                uploadStepSubtext = "Sonuçlar yükleniyor"
            }

            await MainActor.run {
                uploadProgress   = 1.0
                videoId          = id
                isUploading      = false
                navigateToResults = true
            }

        } catch {
            let msg: String
            if error.localizedDescription.lowercased().contains("timed out") ||
               error.localizedDescription.lowercased().contains("time out") {
                msg = "Bağlantı zaman aşımı. Wi-Fi bağlantınızı kontrol edin."
            } else if error.localizedDescription.contains("200 MB") {
                msg = "Video çok büyük. Maksimum boyut 200 MB."
            } else {
                msg = "Yükleme başarısız: \(error.localizedDescription)"
            }
            await MainActor.run {
                errorMessage   = msg
                isUploading    = false
                uploadProgress = 0.0
            }
        }
    }
}

// MARK: - Son Gezi Kartı

struct RecentTripCard: View {
    let video: SavedVideo

    var locationName: String {
        guard let results = video.decodedAIResults,
              let first   = results.nominatim?.deduplicatedLocations?.first else {
            let name = video.filename ?? "Gezi"
            return String(name.prefix(18))
        }
        let n = first.originalName
        return (n.prefix(1).uppercased() + n.dropFirst()).prefix(18).description
    }

    var locationCount: Int {
        video.decodedAIResults?.nominatim?.deduplicatedLocations?.count ?? 0
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            ZStack {
                RoundedRectangle(cornerRadius: 10)
                    .fill(Color.blue.opacity(0.18))
                    .frame(width: 40, height: 40)
                Image(systemName: "map.fill")
                    .foregroundColor(.blue)
                    .font(.callout)
            }

            Text(locationName)
                .font(.caption)
                .fontWeight(.semibold)
                .foregroundColor(.white)
                .lineLimit(2)
                .multilineTextAlignment(.leading)

            HStack(spacing: 4) {
                if locationCount > 0 {
                    Image(systemName: "mappin.circle.fill")
                        .font(.system(size: 9))
                        .foregroundColor(.blue.opacity(0.8))
                    Text("\(locationCount) durak")
                        .font(.caption2)
                        .foregroundColor(.white.opacity(0.45))
                }
                if let date = video.savedAt {
                    if locationCount > 0 { Text("·").font(.caption2).foregroundColor(.white.opacity(0.3)) }
                    Text(date, style: .relative)
                        .font(.caption2)
                        .foregroundColor(.white.opacity(0.45))
                }
            }
        }
        .padding(14)
        .frame(width: 120, height: 118, alignment: .topLeading)
        .background(Color.white.opacity(0.07))
        .cornerRadius(16)
        .overlay(RoundedRectangle(cornerRadius: 16).stroke(Color.white.opacity(0.1), lineWidth: 1))
    }
}

// MARK: - Step View

struct StepView: View {
    let icon: String
    let text: String
    let color: Color

    var body: some View {
        VStack(spacing: 8) {
            ZStack {
                RoundedRectangle(cornerRadius: 12)
                    .fill(color.opacity(0.15))
                    .frame(width: 52, height: 52)
                Image(systemName: icon)
                    .foregroundColor(color)
                    .font(.title3)
            }
            Text(text)
                .font(.caption)
                .foregroundColor(.white.opacity(0.6))
                .multilineTextAlignment(.center)
        }
    }
}

// MARK: - Color Hex Extension

extension Color {
    init(hex: String) {
        let hex = hex.trimmingCharacters(in: CharacterSet.alphanumerics.inverted)
        var int: UInt64 = 0
        Scanner(string: hex).scanHexInt64(&int)
        let a, r, g, b: UInt64
        switch hex.count {
        case 3:  (a, r, g, b) = (255, (int >> 8) * 17, (int >> 4 & 0xF) * 17, (int & 0xF) * 17)
        case 6:  (a, r, g, b) = (255, int >> 16, int >> 8 & 0xFF, int & 0xFF)
        case 8:  (a, r, g, b) = (int >> 24, int >> 16 & 0xFF, int >> 8 & 0xFF, int & 0xFF)
        default: (a, r, g, b) = (255, 0, 0, 0)
        }
        self.init(.sRGB, red: Double(r) / 255, green: Double(g) / 255,
                  blue: Double(b) / 255, opacity: Double(a) / 255)
    }
}

#Preview {
    HomeView().environmentObject(AuthService.shared)
}
