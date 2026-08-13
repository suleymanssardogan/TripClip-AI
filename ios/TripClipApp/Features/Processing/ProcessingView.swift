/// ProcessingView.swift — TripClip
///
/// "Gezi Analizi" / "AI Analiz Ediyor" ekranı.
/// ProcessingViewModel üzerinden polling yapar; elapsed timer LOCAL'dir.

import SwiftUI

// MARK: - ProcessingView

struct ProcessingView: View {

    let videoID:     Int
    var onCompleted: ((Int) -> Void)? = nil

    @StateObject private var vm: ProcessingViewModel
    @Environment(\.dismiss) private var dismiss

    init(videoID: Int, apiClient: APIClientProtocol, token: String,
         onCompleted: ((Int) -> Void)? = nil) {
        self.videoID     = videoID
        self.onCompleted = onCompleted
        _vm = StateObject(wrappedValue: ProcessingViewModel(
            videoID: videoID, apiClient: apiClient, token: token
        ))
    }

    // MARK: Body

    var body: some View {
        ZStack {
            AppColors.background
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
                    .foregroundColor(AppColors.text)

                Text(vm.stage.displaySubtitle)
                    .font(.system(size: 15))
                    .foregroundColor(AppColors.textSecondary)
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
                            .foregroundColor(AppColors.textTertiary)
                        Text(vm.formattedElapsed)
                            .font(.system(size: 13, design: .monospaced))
                            .foregroundColor(AppColors.textTertiary)
                        Text("·  Bu işlem 1–3 dakika sürebilir")
                            .font(.system(size: 13))
                            .foregroundColor(AppColors.textTertiary)
                    }
                    .padding(.bottom, 40)
                }

                // ── Hata / Timeout CTA ─────────────────────────────────────
                // Eskiden bu ekranda sadece bir uyarı metni vardı, aksiyon
                // butonu yoktu — kullanıcı çıkmaz sokakta kalıyordu.
                if case .failed(let msg) = vm.stage {
                    VStack(spacing: 12) {
                        ErrorBanner(message: msg)
                        Button {
                            dismiss()
                        } label: {
                            Text("Geri Dön")
                                .font(.system(size: 15, weight: .semibold))
                                .frame(maxWidth: .infinity)
                                .padding(.vertical, 12)
                        }
                        .background(AppColors.surface2)
                        .foregroundColor(AppColors.text)
                        .cornerRadius(12)
                    }
                    .padding(.horizontal, 24)
                    .padding(.bottom, 32)
                }
                if case .timedOut = vm.stage {
                    VStack(spacing: 12) {
                        ErrorBanner(message: "İşlem zaman aşımına uğradı. Sunucuda hâlâ devam ediyor olabilir.")
                        Button {
                            vm.retryAfterTimeout()
                        } label: {
                            Text("Beklemeye Devam Et")
                                .font(.system(size: 15, weight: .semibold))
                                .frame(maxWidth: .infinity)
                                .padding(.vertical, 12)
                        }
                        .background(AppColors.accentText)
                        .foregroundColor(AppColors.background)
                        .cornerRadius(12)

                        Button {
                            dismiss()
                        } label: {
                            Text("Geri Dön")
                                .font(.system(size: 15, weight: .semibold))
                                .frame(maxWidth: .infinity)
                                .padding(.vertical, 12)
                        }
                        .background(AppColors.surface2)
                        .foregroundColor(AppColors.text)
                        .cornerRadius(12)
                    }
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
        case .done:           return AppColors.success
        case .failed, .timedOut: return AppColors.destructive
        default:
            return AppColors.accentText
        }
    }

    var body: some View {
        ZStack {
            // Arka iz
            Circle()
                .stroke(AppColors.surface2, lineWidth: 6)

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
                    .foregroundColor(AppColors.text)
            }
        }
        // İkon + yüzde metni ayrı parçalar halinde okunuyordu, tamamlanma
        // yüzdesi VoiceOver'a hiçbir zaman anlaşılır biçimde aktarılmıyordu
        // (M36 audit bulgusu — `HomeView`in yükleme halkasındaki AYNI
        // düzeltme).
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(stage.displayTitle)
        .accessibilityValue("Yüzde \(percent)")
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
                          ? AppColors.accentText
                          : AppColors.border)
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
                .foregroundColor(AppColors.destructive)
            Text(message)
                .font(.system(size: 14))
                .foregroundColor(AppColors.text)
        }
        .padding(14)
        .background(AppColors.destructive.opacity(0.18))
        .cornerRadius(12)
    }
}

// MARK: - Preview

#Preview {
    NavigationStack {
        ProcessingView(
            videoID: 99,
            apiClient: APIClient(),
            token: "preview-token"
        )
    }
}
