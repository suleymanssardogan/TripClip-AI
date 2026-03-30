import UIKit
import Social
import UniformTypeIdentifiers

class ShareViewController: UIViewController {
    
    private let baseURL = "http://localhost:8001"
    
    override func viewDidAppear(_ animated: Bool) {
        super.viewDidAppear(animated)
        handleSharedVideo()
    }
    
    func handleSharedVideo() {
        guard let extensionItem = extensionContext?.inputItems.first as? NSExtensionItem,
              let attachments = extensionItem.attachments else {
            dismiss()
            return
        }
        
        // Video attachment'ı bul
        for attachment in attachments {
            if attachment.hasItemConformingToTypeIdentifier(UTType.movie.identifier) {
                attachment.loadItem(forTypeIdentifier: UTType.movie.identifier, options: nil) { [weak self] data, error in
                    guard let self = self else { return }
                    
                    if let url = data as? URL {
                        self.uploadVideo(url: url)
                    } else {
                        self.dismiss()
                    }
                }
                return
            }
        }
        dismiss()
    }
    
    func uploadVideo(url: URL) {
        let boundary = UUID().uuidString
        var request = URLRequest(url: URL(string: "\(baseURL)/api/mobile/videos/upload")!)
        request.httpMethod = "POST"
        request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")
        request.timeoutInterval = 300
        
        guard let videoData = try? Data(contentsOf: url) else {
            dismiss()
            return
        }
        
        var body = Data()
        body.append("--\(boundary)\r\n".data(using: .utf8)!)
        body.append("Content-Disposition: form-data; name=\"file\"; filename=\"video.mp4\"\r\n".data(using: .utf8)!)
        body.append("Content-Type: video/mp4\r\n\r\n".data(using: .utf8)!)
        body.append(videoData)
        body.append("\r\n--\(boundary)--\r\n".data(using: .utf8)!)
        request.httpBody = body
        
        // Yükleniyor göster
        DispatchQueue.main.async {
            self.showLoadingUI()
        }
        
        URLSession.shared.dataTask(with: request) { [weak self] data, response, error in
            DispatchQueue.main.async {
                if error == nil, let data = data,
                   let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                   let videoId = json["id"] as? Int {
                    self?.showSuccess(videoId: videoId)
                } else {
                    self?.showError()
                }
            }
        }.resume()
    }
    
    func showLoadingUI() {
        view.backgroundColor = UIColor(red: 0.04, green: 0.055, blue: 0.153, alpha: 1)
        
        let stack = UIStackView()
        stack.axis = .vertical
        stack.spacing = 16
        stack.alignment = .center
        stack.translatesAutoresizingMaskIntoConstraints = false
        view.addSubview(stack)
        
        let indicator = UIActivityIndicatorView(style: .large)
        indicator.color = .white
        indicator.startAnimating()
        
        let label = UILabel()
        label.text = "TripClip AI'a yükleniyor..."
        label.textColor = .white
        label.font = .systemFont(ofSize: 16, weight: .medium)
        
        stack.addArrangedSubview(indicator)
        stack.addArrangedSubview(label)
        
        NSLayoutConstraint.activate([
            stack.centerXAnchor.constraint(equalTo: view.centerXAnchor),
            stack.centerYAnchor.constraint(equalTo: view.centerYAnchor)
        ])
    }
    
    var videoId: Int = 0

    func showSuccess(videoId: Int) {
        let alert = UIAlertController(
            title: "✅ Yüklendi!",
            message: "Video TripClip AI'a gönderildi.",
            preferredStyle: .alert
        )
        alert.addAction(UIAlertAction(title: "Uygulamayı Aç", style: .default) { _ in
            let url = URL(string: "tripclip://video/\(videoId)")!
            var responder: UIResponder? = self
            while responder != nil {
                if let application = responder as? UIApplication {
                    application.open(url)
                    break
                }
                responder = responder?.next
            }
            self.dismiss()
        })
        alert.addAction(UIAlertAction(title: "Tamam", style: .cancel) { _ in
            self.dismiss()
        })
        present(alert, animated: true)
    }
    
    func showError() {
        let alert = UIAlertController(title: "Hata", message: "Video yüklenemedi. Tekrar deneyin.", preferredStyle: .alert)
        alert.addAction(UIAlertAction(title: "Tamam", style: .default) { _ in
            self.dismiss()
        })
        present(alert, animated: true)
    }
    
    func dismiss() {
        extensionContext?.completeRequest(returningItems: nil, completionHandler: nil)
    }
}
