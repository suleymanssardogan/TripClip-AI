/// ShareViewController.swift — TripClip Share Extension
///
/// UX Akışı:
///   1. Kullanıcı Instagram'da "Paylaş" → TripClip seçer
///   2. Bottom-sheet açılır, URL ayrıştırılırken spinner gösterilir
///   3. URL bulunursa: "TripClip'e Gönder" butonu aktif olur
///   4. Butona basılır →  ekran ANINDA kapanır
///      → completionHandler içinde background upload başlar
///   5. Ana uygulama arka planda sonucu bekler

import UIKit
import Social

// MARK: - ShareViewController

final class ShareViewController: UIViewController {

    // MARK: - State

    private enum ViewState {
        case loading
        case ready(URL)
        case error(String)
    }

    private var state: ViewState = .loading {
        didSet { applyState(state) }
    }

    // MARK: - UI Elements

    private let handleBar: UIView = {
        let v = UIView()
        v.backgroundColor = UIColor.systemGray4
        v.layer.cornerRadius = 2.5
        v.translatesAutoresizingMaskIntoConstraints = false
        return v
    }()

    private let iconView: UIImageView = {
        let iv = UIImageView()
        iv.image = UIImage(systemName: "mappin.and.ellipse")
        iv.tintColor = UIColor(red: 0.40, green: 0.78, blue: 0.96, alpha: 1) // TripClip neon-blue
        iv.contentMode = .scaleAspectFit
        iv.translatesAutoresizingMaskIntoConstraints = false
        return iv
    }()

    private let titleLabel: UILabel = {
        let l = UILabel()
        l.text = "TripClip'e Ekle"
        l.font = .systemFont(ofSize: 17, weight: .semibold)
        l.textColor = .label
        l.translatesAutoresizingMaskIntoConstraints = false
        return l
    }()

    private let subtitleLabel: UILabel = {
        let l = UILabel()
        l.text = "Link aranıyor…"
        l.font = .systemFont(ofSize: 13)
        l.textColor = .secondaryLabel
        l.numberOfLines = 2
        l.textAlignment = .center
        l.translatesAutoresizingMaskIntoConstraints = false
        return l
    }()

    private let spinner: UIActivityIndicatorView = {
        let s = UIActivityIndicatorView(style: .medium)
        s.hidesWhenStopped = true
        s.translatesAutoresizingMaskIntoConstraints = false
        return s
    }()

    private let postButton: UIButton = {
        var config = UIButton.Configuration.filled()
        config.title           = "Video kuyruğa al"
        config.image           = UIImage(systemName: "paperplane.fill")
        config.imagePadding    = 8
        config.cornerStyle     = .capsule
        config.baseBackgroundColor = UIColor(red: 0.40, green: 0.78, blue: 0.96, alpha: 1)
        config.baseForegroundColor = .black
        let btn = UIButton(configuration: config)
        btn.isEnabled = false
        btn.translatesAutoresizingMaskIntoConstraints = false
        return btn
    }()

    private let cancelButton: UIButton = {
        let btn = UIButton(type: .system)
        btn.setTitle("İptal", for: .normal)
        btn.setTitleColor(.secondaryLabel, for: .normal)
        btn.titleLabel?.font = .systemFont(ofSize: 15)
        btn.translatesAutoresizingMaskIntoConstraints = false
        return btn
    }()

    private let cardView: UIView = {
        let v = UIView()
        v.backgroundColor = .systemBackground
        v.layer.cornerRadius = 20
        v.layer.cornerCurve  = .continuous
        v.layer.maskedCorners = [.layerMinXMinYCorner, .layerMaxXMinYCorner]
        v.translatesAutoresizingMaskIntoConstraints = false
        return v
    }()

    // MARK: - Lifecycle

    override func viewDidLoad() {
        super.viewDidLoad()
        setupBackground()
        setupLayout()
        bindActions()
        extractURL()
    }

    // MARK: - Background (translucent overlay)

    private func setupBackground() {
        view.backgroundColor = UIColor.black.withAlphaComponent(0.45)
        let tap = UITapGestureRecognizer(target: self, action: #selector(cancelTapped))
        view.addGestureRecognizer(tap)
        // Kartın kendine tıklamayı geçirme
        cardView.addGestureRecognizer(UITapGestureRecognizer(target: nil, action: nil))
    }

    // MARK: - Layout

    private func setupLayout() {
        view.addSubview(cardView)

        let header = UIStackView(arrangedSubviews: [iconView, titleLabel])
        header.axis    = .horizontal
        header.spacing = 8
        header.alignment = .center
        header.translatesAutoresizingMaskIntoConstraints = false

        [handleBar, header, subtitleLabel, spinner, postButton, cancelButton]
            .forEach { cardView.addSubview($0) }

        NSLayoutConstraint.activate([
            // Card — bottom sheet
            cardView.leadingAnchor.constraint(equalTo: view.leadingAnchor),
            cardView.trailingAnchor.constraint(equalTo: view.trailingAnchor),
            cardView.bottomAnchor.constraint(equalTo: view.bottomAnchor),

            // Handle bar
            handleBar.topAnchor.constraint(equalTo: cardView.topAnchor, constant: 10),
            handleBar.centerXAnchor.constraint(equalTo: cardView.centerXAnchor),
            handleBar.widthAnchor.constraint(equalToConstant: 40),
            handleBar.heightAnchor.constraint(equalToConstant: 5),

            // Icon
            iconView.widthAnchor.constraint(equalToConstant: 28),
            iconView.heightAnchor.constraint(equalToConstant: 28),

            // Header
            header.topAnchor.constraint(equalTo: handleBar.bottomAnchor, constant: 20),
            header.centerXAnchor.constraint(equalTo: cardView.centerXAnchor),

            // Subtitle
            subtitleLabel.topAnchor.constraint(equalTo: header.bottomAnchor, constant: 12),
            subtitleLabel.leadingAnchor.constraint(equalTo: cardView.leadingAnchor, constant: 24),
            subtitleLabel.trailingAnchor.constraint(equalTo: cardView.trailingAnchor, constant: -24),

            // Spinner
            spinner.topAnchor.constraint(equalTo: subtitleLabel.bottomAnchor, constant: 12),
            spinner.centerXAnchor.constraint(equalTo: cardView.centerXAnchor),

            // Post button
            postButton.topAnchor.constraint(equalTo: spinner.bottomAnchor, constant: 20),
            postButton.leadingAnchor.constraint(equalTo: cardView.leadingAnchor, constant: 24),
            postButton.trailingAnchor.constraint(equalTo: cardView.trailingAnchor, constant: -24),
            postButton.heightAnchor.constraint(equalToConstant: 50),

            // Cancel button
            cancelButton.topAnchor.constraint(equalTo: postButton.bottomAnchor, constant: 10),
            cancelButton.centerXAnchor.constraint(equalTo: cardView.centerXAnchor),
            cancelButton.bottomAnchor.constraint(
                equalTo: cardView.safeAreaLayoutGuide.bottomAnchor, constant: -12
            ),
        ])
    }

    // MARK: - Actions

    private func bindActions() {
        postButton.addTarget(self, action: #selector(postTapped),   for: .touchUpInside)
        cancelButton.addTarget(self, action: #selector(cancelTapped), for: .touchUpInside)
    }

    // MARK: - URL Extraction

    private func extractURL() {
        guard let context = extensionContext else {
            state = .error("Extension context bulunamadı.")
            return
        }

        spinner.startAnimating()

        URLExtractor.extract(from: context) { [weak self] result in
            DispatchQueue.main.async {
                switch result {
                case .success(let url): self?.state = .ready(url)
                case .failure(let err): self?.state = .error(err.localizedDescription)
                }
            }
        }
    }

    // MARK: - State → UI

    private func applyState(_ state: ViewState) {
        spinner.stopAnimating()
        postButton.isEnabled = false
        subtitleLabel.textColor = .secondaryLabel

        switch state {
        case .loading:
            spinner.startAnimating()
            subtitleLabel.text = "Instagram linki aranıyor…"

        case .ready(let url):
            subtitleLabel.text = url.host ?? url.absoluteString
            postButton.isEnabled = true

        case .error(let message):
            subtitleLabel.text = message
            subtitleLabel.textColor = .systemRed
        }
    }

    // MARK: - Post Action

    @objc private func postTapped() {
        guard case .ready(let url) = state else { return }

        // Butonu devre dışı bırak — double-tap önlemi
        postButton.isEnabled = false

        // Kullanıcı ID'sini App Group'tan oku (ana uygulama login sırasında yazmış olmalı)
        let userID = UserDefaults(suiteName: BackgroundUploader.Config.appGroupID)?
            .integer(forKey: "currentUserID") ?? 0

        // ─── KRİTİK: completeRequest SONRA background upload ───────────────────
        // completionHandler, extension process suspend edilmeden hemen önce çalışır.
        // Bu pencereyi kullanarak URLSession task'ını başlatıyoruz.
        // Task başladıktan sonra process ölse bile iOS görevi canlı tutar.
        extensionContext?.completeRequest(returningItems: []) { [weak self] _ in
            guard let self else { return }

            BackgroundUploader.shared.enqueue(url: url, userID: userID) { result in
                if case .failure(let error) = result {
                    // Process zaten kapanıyor, loglayabiliriz sadece
                    print("[ShareVC] Enqueue başarısız: \(error.localizedDescription)")
                }
            }
        }
    }

    @objc private func cancelTapped() {
        let cancelError = NSError(
            domain: "com.sardogan.TripClipAI.ShareExtension",
            code: NSUserCancelledError,
            userInfo: nil
        )
        extensionContext?.cancelRequest(withError: cancelError)
    }
}

// MARK: - Presentation Style

/// iOS, Share Extension'ı UIViewController olarak sunar.
/// Şeffaf arka plan + bottom-sheet efekti için custom presentation kullanıyoruz.
extension ShareViewController {
    override func viewWillAppear(_ animated: Bool) {
        super.viewWillAppear(animated)
        // Modal yüksekliğini dinamik içeriğe göre ayarla
        cardView.layoutIfNeeded()
    }
}
