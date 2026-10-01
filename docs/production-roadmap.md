# Production hazırlık planı

Bu belge bir yayın onayı değildir. Domain/sunucu henüz hazır değil; canlı dağıtım yapılmadı.

## 1. Depo ve dağıtım temeli — uygulandı

- Production Compose: SMTP, Google OAuth, APNs, analytics ve asistan ayarları ilgili servislere aktarılıyor.
- Web Google client ID derleme sırasında aktarılıyor; istemci secret almaz.
- JWT/internal secret minimum 32 karakter. Internal secret sabit zamanlı karşılaştırılır.
- Compose gerekli sırlar eksikse durur. `scripts/check-production.py` ayrıca HTTPS origin/host uyumunu, SMTP, reset linkini ve kısmi Google/APNs yapılandırmalarını kontrol eder; değerleri yazdırmaz.
- `.env` dağıtım betiğinde shell olarak çalıştırılmaz.
- Dağıtım, tüm servislerin hazır olmasını bekler ve PostgreSQL/Redis readiness kontrolü başarısızsa hata verir.
- `/health/ready` Nginx üzerinden erişilebilir; smoke teste dahil.
- Web Docker bağlamından `.env*`, yerel bağımlılıklar ve derleme çıktıları çıkarıldı.
- Hesap silme uçları web/mobile BFF ve core API'de eklendi; kullanıcıya ait video, plan, gezi, paylaşım ve oturum kayıtları transaction içinde kaldırılıyor. Web dashboard'da görünür silme kontrolü var.
- Gizlilik ve Kullanım Koşulları sayfaları eklendi (`/privacy`, `/terms`). URL'den indirilen video dosyaları task sonunda temizleniyor.
- Production MongoDB root kimlik doğrulaması, healthcheck ve yedekleme kimlik bilgileri eklendi; Qdrant imajı `v1.7.4` sürümüne sabitlendi ve servis healthcheck'i tanımlandı.

## 2. Otomatik doğrulama — uygulandı, CI uzak sunucuda henüz çalıştırılmadı

Docker build kontrolleri PR'larda da çalışır. CI'a web testleri, TypeScript, production build, sıfır uyarılı lint, iOS XCTest ve dağıtım regresyon testleri eklendi. iOS simülatör testleri ad-hoc imza kullanır; imzayı kapatmak Keychain erişimini bozabilir. Test başına zaman aşımı vardır.

Yerel doğrulamalar:

- Core API: 760 mevcut test ve ayrıca 2 yeni internal-secret başlangıç testi geçti. macOS SciPy 1.15.3 yükleme hatası nedeniyle yalnızca geçici test ortamında SciPy 1.11.4 kullanıldı; requirements değiştirilmedi.
- Web: 115 test geçti; lint/TypeScript/production build başarılı.
- Web BFF: sabitlenmiş bağımlılıklarda 102 mevcut test + 4 production auth testi geçti.
- Mobile BFF: sabitlenmiş bağımlılıklarda 135 mevcut test + 4 production auth testi geçti.
- iOS: 404 test geçti (iOS 26.2 simülatörü, Xcode 26.3).
- Dağıtım/konfigürasyon: 6 regresyon testi geçti.
- Compose: sahte sırlarla yapılandırma doğrulaması geçti; eksik sırlar reddedildi.

Docker daemon kapalı olduğu için konteyner build/başlatma testi yapılmadı. Yerel genel Python ortamı projenin requirements sürümleriyle uyuşmuyor; izole ortam kullanılmalı.

## 3. Yayın öncesi teknik kapılar — henüz tamamlanmadı

0. **Kimlik/veri yaşam döngüsü:** Web/mobile API, web dashboard ve iOS uygulaması hesap silmeyi destekliyor. Silmenin SQL dışındaki analitik kayıtlar, günlükler ve yedekler dahil tüm bağlı verilere etkisi staging ortamında doğrulanmalı. Veri dışa aktarma ihtiyacı ve KVKK metinleri hukuk incelemesinden geçmeli. Yasal sayfalar, işletici kimliği ve iletişim bilgisi girilip `LEGAL_CONTENT_APPROVED=true` olana kadar production dağıtım kontrolünden geçmez.
1. Yerelde geçen tam Core API paketini Linux/Docker üzerinde de geçir.
2. PostgreSQL üzerinde apply/undo/reorder eşzamanlılık testleri; gerçek FK ve kilit davranışı.
3. Backend/frontend bağımlılık ve konteyner güvenlik taraması; bulunan açıkların giderilmesi ve regresyon testleri. Mevcut eski sabitlemelerin güvenli olduğu varsayılmamalı.
4. Redis/Celery kesintisi, worker yeniden başlatılması, yinelenen görev ve yarım video için uçtan uca testler.
5. Yedek al, ayrı boş test veritabanına geri yükle, kullanıcı/gezi/itinerary verilerini karşılaştır. Geri yükleme testi geçmeden yedek stratejisi tamamlanmış sayılmaz.
6. Temsili videolarla gecikme, hata oranı, RAM, kuyruk uzunluğu ve API maliyetini ölç; kullanıcı ve küresel maliyet limitlerini doğrula.
7. Kullanıcı verisi silme/saklama, public paylaşım gizliliği, hesap kurtarma ve oturum iptalinin uçtan uca denetimi.

8. **Altyapı sertleştirme:** Mongo/Qdrant healthcheck ve production auth/pinleme tamamlandı. Mevcut Mongo volume'leri için ilk geçişte root hesabı oluşturma ve staging doğrulaması yapılmalı.

9. **Kuyruk arızası:** Yeni video ve URL analizlerinde iş kaydı video ile aynı SQL işleminde oluşturulur. Kuyruk erişilemiyorsa kayıt korunur ve gönderim yeniden denenir. Gerçek Redis/worker kesintisi staging ortamında ayrıca doğrulanmalı.
10. **Web oturumu:** Access/refresh token'lar HttpOnly çerezlerde tutuluyor; web istemcisi oturum durumunu `/auth/session` üzerinden alıyor. Çerezli giriş, yenileme ve çıkış akışları staging ortamında gerçek tarayıcıyla doğrulanmalı.

## 4. Sunucu ve domain — kullanıcıdan altyapı bilgisi gerekiyor

1. Domain ve Linux sunucusu temin et. Hibrit worker tek başına 8 GB bellek limiti kullanıyor; tüm stack için belgelerdeki eski 4 GB varsayımı yeterli değil. Kesin boyut staging ölçümleriyle seçilmeli.
2. SSH anahtarı, güvenlik duvarı, Docker/Compose, yeterli disk ve sunucu dışı yedek hedefi hazırla.
3. Public DNS ve TLS kur; nginx domainini yapılandır.
4. Üretim `.env` dosyasını sunucuda oluştur. Sırlar sohbete veya Git'e konulmamalı.
5. SMTP hesabı, Gemini anahtarı, Google OAuth redirect adresleri ve APNs üretim bilgilerini sağlayıcı panellerinde yapılandır.
6. iOS Release API adresini seçilen domainle eşleştir. App Icon, imzalama, push entitlement ve gerçek cihaz Share Extension testlerini tamamla.

## 5. Staging — canlıdan önce

Ayrı veritabanı ve test hesaplarıyla deploy et. Kayıt → giriş → video paylaşımı → analiz → mekan kaydetme → gezi → optimize/apply/undo → paylaşım → şifre sıfırlama akışını iOS ve web üzerinden doğrula. Gerçek e-posta, OAuth ve push teslimatını kontrol et. Yük/geri yükleme testlerini burada çalıştır.

## 6. Canlı yayın ve işletim

Staging kapıları geçtikten sonra yedek al; üretime deploy et; smoke testini çalıştır. TLS yenileme, dış uptime alarmı, kuyruk/disk alarmı, sunucu dışı yedek ve geri dönüş prosedürünü işlet. Başarılı bir deploy tek başına üretim yeterliliği değildir.

Teknik dayanaklar: [Docker Compose sağlık bekleme](https://docs.docker.com/reference/cli/docker/compose/up/), [Next.js derleme zamanı ortam değişkenleri](https://nextjs.org/docs/app/guides/self-hosting).
