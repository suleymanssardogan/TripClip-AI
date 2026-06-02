/// ProcessingView.swift — TripClip
///
/// "Gezi Analizi" / "AI Analiz Ediyor" ekranı.
/// ProcessingViewModel üzerinden polling yapar; elapsed timer LOCAL'dir.

import SwiftUI

// MARK: - ProcessingView

struct ProcessingView: View {

    let videoID:    Int
    let apiBaseURL: String
    let authToken:  String
    var onCompleted: ((Int) -> Void)? = nil   // video ID ile geri dön

    @StateObject private var vm: ProcessingViewModel

    init(videoID: Int, apiBaseURL: String, authToken: String,
         onCompleted: ((Int) -> Void)? = nil) {
        self.videoID    = videoID
        self.apiBaseURL = apiBaseURL
        self.authToken  = authToken
        self.onCompleted = onCompleted
        _vm = StateObject(wrappedValue: ProcessingViewModel(
            videoID: videoID, apiBaseURL: apiBaseURL, authToken: authToken
        ))
    }

    // MARK: Body

    var body: some View {
        ZStack {
            // Arka plan — mevcut tasarımla aynı koyu tema
            Color(red: 0.06, green: 0.07, blue: 0.13)
                .ignoresSafeArea()

            VStack(spacing: 0) {
                Spacer()

                // ── Circular Progress ──────────────────────────────────────
                CircularProgressView(
                    percent: vm.stage.percent,
                    stage:   vm.stage
                )
                .frame(width: 160, height: 160)
                .padding(.bottom, 40)

                // ── Stage Title ────────────────────────────────────────────
                Text(vm.stage.displayTitle)
                    .font(.system(size: 24, weight: .bold))
                    .foregroundColor(.white)

                Text(vm.stage.displaySubtitle)
                    .font(.system(size: 15))
                    .foregroundColor(.white.opacity(0.6))
                    .multilineTextAlignment(.center)
                    .padding(.top, 8)
                    .padding(.horizontal, 32)

                // ── Stage Dots ─────────────────────────────────────────────
                StageDotRow(stage: vm.stage)
                    .padding(.top, 32)

                Spacer()

                // ── Elapsed Time (LOCAL) ───────────────────────────────────
                // ⚠️ Düzeltildi: createdAt değil, view açıldığındaki Date() ile hesaplanır.
                // "7d 10s" hatası artık mümkün değil — max 5dk gösterilir.
                if !vm.stage.isTerminal {
                    HStack(spacing: 6) {
                        Image(systemName: "clock")
                            .font(.caption)
                            .foregroundColor(.white.opacity(0.4))
                        Text(vm.formattedElapsed)
                            .font(.system(size: 13, design: .monospaced))
                            .foregroundColor(.white.opacity(0.4))
                        Text("·  Bu işlem 1–3 dakika sürebilir")
                            .font(.system(size: 13))
                            .foregroundColor(.white.opacity(0.4))
                    }
                    .padding(.bottom, 40)
                }

                // ── Hata / Timeout CTA ─────────────────────────────────────
                if case .failed(let msg) = vm.stage {
                    ErrorBanner(message: msg)
                        .padding(.horizontal, 24)
                        .padding(.bottom, 32)
                }
                if case .timedOut = vm.stage {
                    ErrorBanner(message: "İşlem zaman aşımına uğradı. Lütfen tekrar deneyin.")
                        .padding(.horizontal, 24)
                        .padding(.bottom, 32)
                }
            }
        }
        .navigationTitle("Gezi Analizi")
        .navigationBarTitleDisplayMode(.inline)
        .onAppear  { vm.startMonitoring() }
        .onDisappear { vm.stopMonitoring() }
        .onChange(of: vm.stage) { newStage in
            if case .done = newStage {
                onCompleted?(videoID)
            }
        }
    }
}

// MARK: - CircularProgressView

private struct CircularProgressView: View {
    let percent: Int
    let stage:   ProgressStage

    private var progress: Double { Double(percent) / 100.0 }

    private var strokeColor: Color {
        switch stage {
        case .done:           return .green
        case .failed, .timedOut: return .red
        default:
            return Color(red: 0.55, green: 0.35, blue: 0.95)  // mor-mavi gradyan rengi
        }
    }

    var body: some View {
        ZStack {
            // Arka iz
            Circle()
                .stroke(Color.white.opacity(0.1), lineWidth: 6)

            // İlerleme yayı
            Circle()
                .trim(from: 0, to: progress)
                .stroke(
                    strokeColor,
                    style: StrokeStyle(lineWidth: 6, lineCap: .round)
                )
                .rotationEffect(.degrees(-90))
                .animation(.easeInOut(duration: 0.4), value: percent)

            // İkon + yüzde
            VStack(spacing: 4) {
                Image(systemName: stageIcon)
                    .font(.system(size: 32))
                    .foregroundColor(strokeColor)
                    .symbolEffect(.pulse, isActive: !stage.isTerminal)

                Text("%\(percent)")
                    .font(.system(size: 15, weight: .semibold, design: .rounded))
                    .foregroundColor(.white.opacity(0.85))
            }
        }
    }

    private var stageIcon: String {
        switch stage {
        case .uploading:    return "arrow.up.circle"
        case .queued:       return "clock.circle"
        case .downloading:  return "arrow.down.circle"
        case .processing:   return "cpu"
        case .done:         return "checkmark.circle.fill"
        case .failed, .timedOut: return "exclamationmark.circle.fill"
        }
    }
}

// MARK: - StageDotRow

private struct StageDotRow: View {
    let stage: ProgressStage

    private let allStages: [ProgressStage] = [
        .uploading, .queued, .downloading,
        .processing(percent: 0),
        .done
    ]

    private func isActive(_ s: ProgressStage) -> Bool {
        stageOrder(stage) >= stageOrder(s)
    }

    private func stageOrder(_ s: ProgressStage) -> Int {
        switch s {
        case .uploading:    return 0
        case .queued:       return 1
        case .downloading:  return 2
        case .processing:   return 3
        case .done:         return 4
        default:            return -1
        }
    }

    var body: some View {
        HStack(spacing: 8) {
            ForEach(0..<allStages.count, id: \.self) { i in
                Circle()
                    .fill(isActive(allStages[i])
                          ? Color(red: 0.22, green: 0.55, blue: 0.95)
                          : Color.white.opacity(0.2))
                    .frame(width: 8, height: 8)
                    .animation(.easeInOut, value: stage.percent)
            }
        }
    }
}

// MARK: - ErrorBanner

private struct ErrorBanner: View {
    let message: String
    var body: some View {
        HStack {
            Image(systemName: "exclamationmark.triangle.fill")
                .foregroundColor(.orange)
            Text(message)
                .font(.system(size: 14))
                .foregroundColor(.white.opacity(0.85))
        }
        .padding(14)
        .background(Color.red.opacity(0.18))
        .cornerRadius(12)
    }
}

// MARK: - Preview

#Preview {
    NavigationStack {
        ProcessingView(
            videoID: 99,
            apiBaseURL: "http://localhost:8001",
            authToken: "preview-token"
        )
    }
}
