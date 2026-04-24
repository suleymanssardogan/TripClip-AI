import UIKit
import UniformTypeIdentifiers

// MARK: - Share Extension Ana Controller
// Instagram'dan (veya başka uygulamalardan) paylaş butonuna basıldığında
// TripClip AI seçilince bu controller devreye girer.

class ShareViewController: UIViewController {

    private let baseURL      = "http://127.0.0.1:8001"
    private let appScheme    = "tripclip"

    // MARK: - Lifecycle

    override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = UIColor(red: 0.04, green: 0.055, blue: 0.153, alpha: 1)
        showSplash()
    }

    override func viewDidAppear(_ animated: Bool) {
        super.viewDidAppear(animated)
        handleSharedContent()
    }

    // MARK: - İçerik Türünü Belirle

    func handleSharedContent() {
        guard let extensionItem = extensionContext?.inputItems.first as? NSExtensionItem,
              let attachments   = extensionItem.attachments else {
            finish()
            return
        }

        for attachment in attachments {
            // 1) Video dosyası (galeriden doğrudan paylaş)
            if attachment.hasItemConformingToTypeIdentifier(UTType.movie.identifier) {
                attachment.loadItem(forTypeIdentifier: UTType.movie.identifier) { [weak self] item, _ in
                    if let url = item as? URL {
                        self?.handleVideo(url: url)
                    } else {
                        self?.showError("Video açılamadı.")
                    }
                }
                return
            }

            // 2) URL (Instagram Reels paylaş → uygulama listesi → TripClip AI)
            if attachment.hasItemConformingToTypeIdentifier(UTType.url.identifier) {
                attachment.loadItem(forTypeIdentifier: UTType.url.identifier) { [weak self] item, _ in
                    if let url = item as? URL {
                        DispatchQueue.main.async { self?.handleURL(url) }
                    } else {
                        self?.finish()
                    }
                }
                return
            }

            // 3) Düz metin (bazı uygulamalar URL'i text olarak paylaşır)
            if attachment.hasItemConformingToTypeIdentifier(UTType.plainText.identifier) {
                attachment.loadItem(forTypeIdentifier: UTType.plainText.identifier) { [weak self] item, _ in
                    if let text = item as? String, let url = URL(string: text) {
                        DispatchQueue.main.async { self?.handleURL(url) }
                    } else {
                        self?.finish()
                    }
                }
                return
            }
        }

        finish()
    }

    // MARK: - Video Yükleme

    func handleVideo(url: URL) {
        DispatchQueue.main.async { self.showLoading(message: "Video yükleniyor...") }

        guard let videoData = try? Data(contentsOf: url) else {
            showError("Video okunamadı.")
            return
        }

        let boundary = UUID().uuidString
        var request  = URLRequest(url: URL(string: "\(baseURL)/api/mobile/videos/upload")!)
        request.httpMethod = "POST"
        request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")
        request.timeoutInterval = 300

        // Keychain'den token al (main app ile aynı keychain)
        if let token = keychainToken() {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }

        var body = Data()
        body.append("--\(boundary)\r\n".data(using: .utf8)!)
        body.append("Content-Disposition: form-data; name=\"file\"; filename=\"video.mp4\"\r\n".data(using: .utf8)!)
        body.append("Content-Type: video/mp4\r\n\r\n".data(using: .utf8)!)
        body.append(videoData)
        body.append("\r\n--\(boundary)--\r\n".data(using: .utf8)!)
        request.httpBody = body

        URLSession.shared.dataTask(with: request) { [weak self] data, response, error in
            DispatchQueue.main.async {
                if let data,
                   let json     = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                   let videoId  = json["id"] as? Int {
                    self?.showSuccess(videoId: videoId, message: "Video analiz için gönderildi!")
                } else {
                    self?.showError("Yükleme başarısız. Uygulamayı açarak tekrar deneyin.")
                }
            }
        }.resume()
    }

    // MARK: - URL İşleme (Instagram Reels vb.)

    func handleURL(_ url: URL) {
        let isInstagram = url.host?.contains("instagram.com") == true
        let isReels     = url.pathComponents.contains("reel") || url.pathComponents.contains("reels")

        if isInstagram {
            showURLReceived(
                icon:    "camera.filters",
                title:   isReels ? "Reels Alındı" : "Instagram Bağlantısı",
                message: "TripClip AI bu bağlantıyı kaydetti.\nUygulama açılıyor...",
                url:     url
            )
        } else {
            showURLReceived(
                icon:    "link.circle.fill",
                title:   "Bağlantı Alındı",
                message: "TripClip AI bu bağlantıyı kaydetti.\nUygulama açılıyor...",
                url:     url
            )
        }
    }

    // MARK: - UI

    private func showSplash() {
        let logo = UILabel()
        logo.text = "✈️ TripClip AI"
        logo.font = .systemFont(ofSize: 22, weight: .bold)
        logo.textColor = .white
        logo.textAlignment = .center
        logo.translatesAutoresizingMaskIntoConstraints = false
        view.addSubview(logo)
        NSLayoutConstraint.activate([
            logo.centerXAnchor.constraint(equalTo: view.centerXAnchor),
            logo.centerYAnchor.constraint(equalTo: view.centerYAnchor),
        ])
    }

    private func showLoading(message: String) {
        view.subviews.forEach { $0.removeFromSuperview() }

        let stack = UIStackView()
        stack.axis = .vertical; stack.spacing = 16; stack.alignment = .center
        stack.translatesAutoresizingMaskIntoConstraints = false
        view.addSubview(stack)

        let indicator = UIActivityIndicatorView(style: .large)
        indicator.color = UIColor(red: 0.3, green: 1.0, blue: 0.76, alpha: 1)
        indicator.startAnimating()

        let label  = makeLabel(message, size: 16, weight: .medium)
        let cancel = makeButton("İptal") { [weak self] in self?.finish() }

        [indicator, label, cancel].forEach { stack.addArrangedSubview($0) }
        NSLayoutConstraint.activate([
            stack.centerXAnchor.constraint(equalTo: view.centerXAnchor),
            stack.centerYAnchor.constraint(equalTo: view.centerYAnchor),
        ])
    }

    private func showURLReceived(icon: String, title: String, message: String, url: URL) {
        view.subviews.forEach { $0.removeFromSuperview() }

        let stack = UIStackView()
        stack.axis = .vertical; stack.spacing = 20; stack.alignment = .center
        stack.translatesAutoresizingMaskIntoConstraints = false
        view.addSubview(stack)

        // Icon
        let img = UIImageView(image: UIImage(systemName: icon))
        img.tintColor = UIColor(red: 0.3, green: 1.0, blue: 0.76, alpha: 1)
        img.contentMode = .scaleAspectFit
        img.widthAnchor.constraint(equalToConstant: 56).isActive = true
        img.heightAnchor.constraint(equalToConstant: 56).isActive = true

        let titleLabel   = makeLabel(title, size: 20, weight: .bold)
        let messageLabel = makeLabel(message, size: 14, weight: .regular, alpha: 0.7)
        messageLabel.numberOfLines = 0
        messageLabel.textAlignment = .center

        let openBtn = makeButton("Uygulamayı Aç") { [weak self] in
            self?.openApp(with: url)
        }
        let cancelBtn = makeButton("Kapat", primary: false) { [weak self] in
            self?.finish()
        }

        [img, titleLabel, messageLabel, openBtn, cancelBtn].forEach { stack.addArrangedSubview($0) }
        NSLayoutConstraint.activate([
            stack.centerXAnchor.constraint(equalTo: view.centerXAnchor),
            stack.centerYAnchor.constraint(equalTo: view.centerYAnchor),
            stack.leadingAnchor.constraint(equalTo: view.leadingAnchor, constant: 32),
            stack.trailingAnchor.constraint(equalTo: view.trailingAnchor, constant: -32),
        ])

        // Kısa bir süre sonra otomatik aç
        DispatchQueue.main.asyncAfter(deadline: .now() + 1.5) { [weak self] in
            self?.openApp(with: url)
        }
    }

    func showSuccess(videoId: Int, message: String) {
        view.subviews.forEach { $0.removeFromSuperview() }

        let stack = UIStackView()
        stack.axis = .vertical; stack.spacing = 20; stack.alignment = .center
        stack.translatesAutoresizingMaskIntoConstraints = false
        view.addSubview(stack)

        let check = UILabel(); check.text = "✅"; check.font = .systemFont(ofSize: 48)
        let label = makeLabel(message, size: 16, weight: .medium)

        let openBtn = makeButton("Sonuçları Gör") { [weak self] in
            self?.openApp(videoId: videoId)
        }
        let doneBtn = makeButton("Tamam", primary: false) { [weak self] in
            self?.finish()
        }

        [check, label, openBtn, doneBtn].forEach { stack.addArrangedSubview($0) }
        NSLayoutConstraint.activate([
            stack.centerXAnchor.constraint(equalTo: view.centerXAnchor),
            stack.centerYAnchor.constraint(equalTo: view.centerYAnchor),
        ])
    }

    func showError(_ message: String) {
        DispatchQueue.main.async {
            let alert = UIAlertController(title: "Hata", message: message, preferredStyle: .alert)
            alert.addAction(UIAlertAction(title: "Tamam", style: .default) { [weak self] _ in self?.finish() })
            self.present(alert, animated: true)
        }
    }

    // MARK: - Deep Link

    private func openApp(videoId: Int) {
        openApp(with: URL(string: "\(appScheme)://\(videoId)")!)
    }

    private func openApp(with url: URL) {
        // Encoded URL ile uygulamayı aç
        let encoded = url.absoluteString.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? ""
        let deepLink = URL(string: "\(appScheme)://share?url=\(encoded)") ?? URL(string: "\(appScheme)://")!

        var responder: UIResponder? = self
        while let r = responder {
            if let app = r as? UIApplication {
                app.open(deepLink)
                break
            }
            responder = r.next
        }
        finish()
    }

    private func finish() {
        extensionContext?.completeRequest(returningItems: nil, completionHandler: nil)
    }

    // MARK: - Keychain

    private func keychainToken() -> String? {
        let query: [CFString: Any] = [
            kSecClass:            kSecClassGenericPassword,
            kSecAttrAccount:      "tripclip_access_token",
            kSecReturnData:       true,
            kSecMatchLimit:       kSecMatchLimitOne,
        ]
        var result: AnyObject?
        guard SecItemCopyMatching(query as CFDictionary, &result) == errSecSuccess,
              let data  = result as? Data,
              let token = String(data: data, encoding: .utf8) else { return nil }
        return token
    }

    // MARK: - UI Helpers

    private func makeLabel(_ text: String, size: CGFloat, weight: UIFont.Weight, alpha: CGFloat = 1) -> UILabel {
        let l = UILabel()
        l.text = text; l.font = .systemFont(ofSize: size, weight: weight)
        l.textColor = UIColor.white.withAlphaComponent(alpha)
        l.textAlignment = .center
        return l
    }

    private func makeButton(_ title: String, primary: Bool = true, action: @escaping () -> Void) -> UIButton {
        if primary {
            var config                        = UIButton.Configuration.filled()
            config.title                      = title
            config.baseBackgroundColor        = UIColor(red: 0.3, green: 1.0, blue: 0.76, alpha: 1)
            config.baseForegroundColor        = UIColor(red: 0.04, green: 0.055, blue: 0.153, alpha: 1)
            config.contentInsets              = NSDirectionalEdgeInsets(top: 12, leading: 28, bottom: 12, trailing: 28)
            config.titleTextAttributesTransformer = UIConfigurationTextAttributesTransformer { attrs in
                var a = attrs; a.font = UIFont.systemFont(ofSize: 15, weight: .semibold); return a
            }
            config.cornerStyle                = .medium
            let btn                           = UIButton(configuration: config)
            btn.addAction(UIAction { _ in action() }, for: .touchUpInside)
            return btn
        } else {
            let btn = UIButton(type: .system)
            btn.setTitle(title, for: .normal)
            btn.titleLabel?.font = .systemFont(ofSize: 15, weight: .semibold)
            btn.setTitleColor(UIColor.white.withAlphaComponent(0.5), for: .normal)
            btn.addAction(UIAction { _ in action() }, for: .touchUpInside)
            return btn
        }
    }
}
