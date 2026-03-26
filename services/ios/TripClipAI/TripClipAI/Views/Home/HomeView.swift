import SwiftUI
import PhotosUI

struct HomeView: View {
    @State private var selectedItem: PhotosPickerItem?
    @State private var isUploading = false
    @State private var videoId: Int?
    @State private var errorMessage: String?
    @State private var navigateToResults = false
    @State private var animateLogo = false
    
    var body: some View {
        NavigationStack {
            ZStack {
                // Gradient arka plan
                LinearGradient(
                    colors: [Color(hex: "0A0E27"), Color(hex: "1a1a4e"), Color(hex: "0d2137")],
                    startPoint: .topLeading,
                    endPoint: .bottomTrailing
                )
                .ignoresSafeArea()
                
                VStack(spacing: 0) {
                    Spacer()
                    
                    // Logo
                    VStack(spacing: 16) {
                        ZStack {
                            Circle()
                                .fill(Color.blue.opacity(0.15))
                                .frame(width: 120, height: 120)
                            Circle()
                                .fill(Color.blue.opacity(0.08))
                                .frame(width: 160, height: 160)
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
                    
                    // Nasıl Çalışır
                    HStack(spacing: 24) {
                        StepView(icon: "video.fill", text: "Video\nSeç", color: .blue)
                        Image(systemName: "arrow.right")
                            .foregroundColor(.white.opacity(0.3))
                        StepView(icon: "cpu.fill", text: "AI\nAnaliz", color: .purple)
                        Image(systemName: "arrow.right")
                            .foregroundColor(.white.opacity(0.3))
                        StepView(icon: "map.fill", text: "Plan\nAl", color: .green)
                    }
                    .padding(.bottom, 40)
                    
                    // Upload butonu
                    if isUploading {
                        VStack(spacing: 12) {
                            ProgressView()
                                .tint(.white)
                                .scaleEffect(1.3)
                            Text("Video yükleniyor...")
                                .foregroundColor(.white.opacity(0.7))
                                .font(.subheadline)
                        }
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 20)
                    } else {
                        PhotosPicker(selection: $selectedItem, matching: .videos) {
                            HStack(spacing: 12) {
                                Image(systemName: "video.badge.plus")
                                    .font(.headline)
                                Text("Video Seç ve Planla")
                                    .font(.headline)
                                    .fontWeight(.semibold)
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
                    
                    if let error = errorMessage {
                        Text(error)
                            .foregroundColor(.red.opacity(0.8))
                            .font(.caption)
                            .padding(.top, 8)
                    }
                    
                    Spacer().frame(height: 50)
                }
            }
            .navigationBarHidden(true)
            .onAppear { animateLogo = true }
            .onChange(of: selectedItem) { _, newItem in
                guard let item = newItem else { return }
                Task { await uploadVideo(item: item) }
            }
            .navigationDestination(isPresented: $navigateToResults) {
                if let id = videoId {
                    ResultsView(videoId: id)
                }
            }
        }
    }
    
    func uploadVideo(item: PhotosPickerItem) async {
        isUploading = true
        errorMessage = nil
        do {
            guard let data = try await item.loadTransferable(type: Data.self) else {
                throw URLError(.badServerResponse)
            }
            let tempURL = FileManager.default.temporaryDirectory
                .appendingPathComponent(UUID().uuidString + ".mp4")
            try data.write(to: tempURL)
            let id = try await APIService.shared.uploadVideo(fileURL: tempURL)
            await MainActor.run {
                videoId = id
                isUploading = false
                navigateToResults = true
            }
        } catch {
            await MainActor.run {
                errorMessage = "Hata: \(error.localizedDescription)"
                isUploading = false
            }
        }
    }
}

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

extension Color {
    init(hex: String) {
        let hex = hex.trimmingCharacters(in: CharacterSet.alphanumerics.inverted)
        var int: UInt64 = 0
        Scanner(string: hex).scanHexInt64(&int)
        let a, r, g, b: UInt64
        switch hex.count {
        case 3: (a, r, g, b) = (255, (int >> 8) * 17, (int >> 4 & 0xF) * 17, (int & 0xF) * 17)
        case 6: (a, r, g, b) = (255, int >> 16, int >> 8 & 0xFF, int & 0xFF)
        case 8: (a, r, g, b) = (int >> 24, int >> 16 & 0xFF, int >> 8 & 0xFF, int & 0xFF)
        default: (a, r, g, b) = (255, 0, 0, 0)
        }
        self.init(.sRGB, red: Double(r)/255, green: Double(g)/255, blue: Double(b)/255, opacity: Double(a)/255)
    }
}

#Preview {
    HomeView()
}
