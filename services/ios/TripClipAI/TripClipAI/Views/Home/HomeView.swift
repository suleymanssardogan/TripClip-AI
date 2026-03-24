import SwiftUI
import PhotosUI

struct HomeView: View {
    @State private var selectedItem: PhotosPickerItem?
    @State private var isUploading = false
    @State private var videoId: Int?
    @State private var errorMessage: String?
    @State private var navigateToResults = false
    
    var body: some View {
        NavigationStack {
            VStack(spacing: 30) {
                
                // Logo & Başlık
                VStack(spacing: 12) {
                    Image(systemName: "mappin.and.ellipse")
                        .font(.system(size: 60))
                        .foregroundColor(.blue)
                    
                    Text("TripClip AI")
                        .font(.largeTitle)
                        .fontWeight(.bold)
                    
                    Text("Gezi videolarından otomatik seyahat planı")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                        .multilineTextAlignment(.center)
                }
                .padding(.top, 60)
                
                Spacer()
                
                // Upload Butonu
                if isUploading {
                    VStack(spacing: 16) {
                        ProgressView()
                            .scaleEffect(1.5)
                        Text("Video işleniyor...")
                            .font(.subheadline)
                            .foregroundColor(.secondary)
                    }
                } else {
                    PhotosPicker(
                        selection: $selectedItem,
                        matching: .videos
                    ) {
                        HStack {
                            Image(systemName: "video.badge.plus")
                            Text("Video Seç")
                        }
                        .font(.headline)
                        .foregroundColor(.white)
                        .frame(maxWidth: .infinity)
                        .padding()
                        .background(Color.blue)
                        .cornerRadius(16)
                        .padding(.horizontal, 30)
                    }
                }
                
                // Hata mesajı
                if let error = errorMessage {
                    Text(error)
                        .foregroundColor(.red)
                        .font(.caption)
                }
                
                Spacer()
            }
            .navigationTitle("")
            .navigationBarHidden(true)
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
            
            // Temp dosyaya yaz
            let tempURL = FileManager.default.temporaryDirectory
                .appendingPathComponent(UUID().uuidString + ".mp4")
            try data.write(to: tempURL)
            
            // Upload et
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

#Preview {
    HomeView()
}
