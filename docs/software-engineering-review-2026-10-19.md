# TripClip AI — yazılım mühendisliği incelemesi

## 20 Ekim güncellemesi — kalite kapıları

- Web lint hatası ve kullanılmayan import düzeltildi; sıfır uyarılı lint ve TypeScript kontrolü geçti.
- NER'nin transformers importu model oluşturulana ertelendi. Test collection artık SciPy binary yüklemesine bağlı değil; gerçek ML runtime'ın sağlığı ayrıca doğrulanmalı.
- NER import izolasyonu için regresyon testi eklendi.
- URL migration testi yalnızca hedef migration'a yükseltiliyor; mevcut metadata'ya daha sonraki Apple kolonunu tekrar eklemeye çalışmıyor.
- Places scoring testi gerçek kullanılan HTTP adaptörünü mock'luyor; dış ağa bağımlı eski patch kaldırıldı.
- İlgili 11 test geçti. Tam Core paketine başarılı denmedi: ilk koşuyla çakışan ayrı NER koşusunun session teardown'u ortak SQLite tablolarını sildi. Sonraki tek-süreçli koşu %81'i geçip devam etti ancak çok yavaşladığı için kesildi. Test veritabanı izolasyonu ve yavaş bağımlılıkların ayrılması sonraki iştir.
- Docker konteynerleri başlatılmadı; mevcut kullanıcı ve analiz kayıtlarına müdahale edilmedi.

Tarih: 19 Ekim 2026. Temel commit: `94b2411`; mevcut yerel değişiklikler de incelendi.

Bu belge yayın onayı veya her satırın denetlendiği iddiası değildir. Kod, sözleşmeler, güven sınırları ve kritik yaşam döngüleri üzerinde ilk uçtan uca incelemedir. Bu turda ürün kodu değiştirilmedi. Eski raporlardaki test sayıları bugünkü kanıt olarak kullanılmadı.

## 1. Sistemin haritası: sorumluluk ayrımı

iOS/Web → Mobile/Web BFF → Core API → PostgreSQL'deki iş kaydı → Celery → analiz sağlayıcıları → sonuç → istemciler.

PostgreSQL ana iş verisini, Redis kuyruk/cache/ilerlemeyi, Qdrant türetilmiş arama indeksini tutuyor. MongoDB ve vektör indeksinin gerçek kullanım gereksinimi ayrıca ölçülmeli; her veri deposu işletim maliyeti getirir.

İyi: istemciye özel dönüşümler BFF'de, iş mantığı Core'da. Repository arayüzleri ve DI test edilebilirliği artırıyor. Yeni servisler çıkarmak yerine mevcut modüler yapıyı güçlendirmek daha uygun.

Öğrenme: modülerlik klasör sayısı değildir; bir değişikliğin kaç bağımsız parçayı değiştirmeyi gerektirdiğidir.

## 2. Öncelikli bulgular

### P1 — Konum güvenliği tüm sonuca uygulanmıyor

Kanıt: `app/ml/places_service.py:enrich_locations` yeni doğrulayıcıyı çağırıyor; `app/core/services/pipeline/locations.py:_convert_vision_landmarks` koordinatları doğrudan dönüştürüyor. `_fix_geographic_outliers` doğrudan `search_place` ile yeni sonuç oluşturabiliyor. Bu yollar aynı son doğrulama sınırından geçmiyor. `video_processor.py` bunları birleştirip rotaya gönderiyor.

Etki: normal geocoding yolu güvenli olsa bile başka bir sağlayıcı veya sonradan düzeltme yanlış pini tekrar sokabilir. Bu, somut bir yeni yanlış koordinat gözlemi değil, doğrulanmış kapsam boşluğudur.

Çözüm: bütün sağlayıcılardan ve düzeltmelerden SONRA, dedup/rota/kayıttan ÖNCE tek doğrulama kapısı. Yer bazında ilçe/ülke bağlamını o noktaya kadar taşı. Başarısızları sebepleriyle ayrı tut.

Kabul: aynı yanlış koordinat NER, OCR, Vision ve outlier düzeltmesi üzerinden ayrı ayrı verildiğinde hiçbirinde rota veya Library kaydı oluşmamalı. Çok şehirli doğru video yanlışlıkla tek şehre zorlanmamalı.

İlke: invariant, sistemin hangi yoldan gelirse gelsin koruduğu kuraldır.

### P1 — Mobil upload limiti belleğe almadan önce uygulanmıyor

Kanıt: `services/mobile-bff/app/routes/videos.py:upload_video`, `await file.read()` sonrasında 100 MB kontrolü yapıyor. Core aynı dosyayı sınırlı `read(MAX_UPLOAD_BYTES + 1)` ile okuyor.

Etki: eşzamanlı büyük istekler BFF belleğini zorlayabilir; Core'daki sınır önceki katmanı korumaz. Gerçek yük saldırısı yapılmadı.

Çözüm: BFF'de sınırlı okuma; proxy sınırı, süre ve eşzamanlılık sınırlarını uyumlu hale getirme. İleride disk/obje deposuna akış değerlendirilebilir.

Kabul: limit+1 dosya 413/uyumlu hata ile reddedilmeli; Core'a iletilmemeli. Sınır altı gerçek video çalışmalı.

### P1 — Şimdiki yerel web değişiklikleri CI lint kapısını geçmiyor

Kanıt: `npm run lint -- --max-warnings=0`: `analyze/[id]/page.tsx` içinde effect gövdesindeki `setTipsRefreshStopped(false)` lint hatası; kullanılmayan `Globe2` importu uyarı. Bunlar son yaptığımız değişikliklerde kaldı.

Etki: 122 web testi geçse de CI başarısız olur. Önceki tip kontrolü bu hatayı yakalamaz.

Çözüm: effect durum sıfırlamasını uygun yaşam döngüsüne taşı, kullanılmayan importu kaldır; lint ve tip kontrolünü birlikte çalıştır.

İlke: kalite kapıları birbirinin yerine geçmez.

### P2 — Süresi dolan web oturumu anonim istek gibi davranabiliyor

Kanıt: `services/web-bff/app/core/auth.py:get_optional_user_id` geçersiz token hatasını yutup None döndürüyor. Core özel video için bilinçli olarak 404 veriyor. Web error wrapper genel `NOT_FOUND` kodunu 404 eşlemesine almıyor; genel 400 mesajına düşüyor. Kullanıcı oturum açınca aynı kayıt açıldı.

Çözüm: public anonim erişimi koruyarak mevcut ama geçersiz token'ı 401 yap; frontend refresh/yeniden giriş akışını çalıştır. Gerçek anonim özel-video isteğinde varlık bilgisini sızdırma. `NOT_FOUND` eşlemesini düzelt.

Kabul: expired session → refresh veya giriş; anonim ve başka kullanıcı → özel kayda erişemez; public kayıt anonim açılır.

### P2 — Mobil JWT doğrulaması web/Core ile aynı sözleşmede değil

Kanıt: `services/mobile-bff/app/core/auth.py:get_current_user_id` `type=access` kontrolü yapmıyor; `sub` eksik/bozuksa KeyError/ValueError açıkta. Yerel, yapay, geçerli imzalı `type=refresh` JWT aynı helper'dan geçti.

Sınır: gerçek refresh token'lar opak rastgele değerler (`core-api/app/core/auth.py:generate_refresh_token`); bu nedenle gerçek refresh token ile erişim açığı kanıtlanmış değildir. JWT üretebilmek için imza sırrı gerekir. Bulgu token sözleşmesi ve hata dayanıklılığı eksikliğidir.

Kabul: yanlış tür, eksik/bozuk sub, expired ve bozuk imza tutarlı 401; geçerli access token çalışır.

### P2 — Video sonucu ile Library senkronizasyonu arasında kalıcı boşluk kalabilir

Kanıt: `SqlVideoRepository.save_results` videoyu tamamlayıp commit ediyor, ardından `sync_from_video` hatasını yakalayıp yalnızca logluyor. Place oluştuğunda indeks işi transaction ile kalıcı; fakat Place senkronizasyonunun kendisi aynı kurtarma güvencesinde değil.

Etki: sonuç görünürken kullanıcının Library'si eksik kalabilir.

Çözüm: video transaction'ında `library_sync` outbox işi; idempotent worker ve uzlaşma taraması.

Kabul: senkronizasyon ortasında DB hatası/worker kapanması sonrası tekrar çalışmada eksik kayıt tamamlanmalı, çift save oluşmamalı.

### P2 — Konum kalitesi istemciler arasında eksik taşınıyor

Kanıt: mobil `LocationPin` dönüşümü precision taşıyor; web `_web_locations` alanı düşürüyor. Yeni unresolved kayıtlar gösteriliyor ancak eski approximate pinler bu değişiklikle yeniden değerlendirilmiş olmuyor.

Çözüm: tek kalite sözleşmesi, web/iOS ortak fixture testleri, eski kayıtlar için kontrollü yeniden değerlendirme. Kullanıcının kayıtlarını sessizce değiştirme.

### P2 — RAG ve genel model önerisi ürün dilinde karışıyor

Kanıt: `RAGService` kendisi retrieval yapmadığını açıkça belirtiyor. Gerçek retrieval TripAssistantService ve bilgi getirici katmanda. Gemini travel tips coğrafi bağlam alıyor ama harici bilgi kaynağı sağlamıyor. UI istatistiklerinde hâlâ “RAG sistemi” ifadesi var.

Çözüm: genel öneri ile kaynaklı cevap ayrımı; kaynaklı cevapta document/place kimliği ve alıntı doğrulaması. Prompt'a “uydurma” yazmak doğruluk kontrolü değildir. İsim filtreleme serbest özet metnini doğrulamaz.

## 3. İyi yapılan mühendislik kararları

- SQL outbox, lease ve bounded retry: Redis'e gönderim başarısız olduğunda iş kaydı kaybolmuyor.
- Public erişim açık yayın kararına bağlı; özel video varlığını gizleyen 404 bilinçli bir güvenlik tercihi.
- Internal secret sabit zamanlı karşılaştırılıyor; production'da eksik/zayıf secret başlangıcı durduruyor.
- Web HttpOnly çerez, iOS Keychain ve sürümlü AI paylaşım izni mevcut.
- Hesap silmede SQL transaction, dosya silme kuyruğu ve Apple iptal işi mevcut. Bunların tüm dış sistemler/yedekler üzerinde tamamlandığı bu turda doğrulanmadı.
- CI web/BFF/Core/iOS ve gerçek altyapı dayanıklılık testlerini içeriyor. CI dosyasının bulunması son uzak koşunun başarılı olduğunu kanıtlamaz.
- Integration testlerinde gerçek PostgreSQL kilidi, broker kesintisi, worker ölümü ve duplicate iş senaryoları var.

## 4. Test kanıtı — bu inceleme turu

| Kontrol | Sonuç |
|---|---|
| Web tam birim paketi | 122 geçti |
| Mobile BFF tam paket | 144 geçti |
| Web BFF tam paket | 121 geçti |
| Core seçili pagination/HTTP pool + location validation + internal auth | 25 geçti |
| Web lint, sıfır uyarı | 1 hata, 1 uyarı |
| Core tam paket | Collection aşamasında durdu: NER → transformers → SciPy macOS binary import hatası |

Core tam paket sonucu uygulama assertion hatası veya başarılı test koşusu değildir; ortam kaynaklı engeldir. Linux/izole ortamda tekrarlanmalı. Önceden görülen pagination hataları bu seçili koşuda tekrar etmedi.

Bu turda iOS testleri/cihaz etkileşimleri, production build, dependency/CVE taraması, yük testi, restore veya gerçek dış sağlayıcı çağrıları çalıştırılmadı. Mevcut kullanıcı/veriler silinmedi. KVKK/App Store uygunluğu hakkında onay verilmedi.

## 5. Adım adım öğrenme ve düzeltme sırası

1. **Kalite kapıları:** lint ve tekrarlanabilir Core test ortamı. Öğren: red/green döngüsü ve ortam izolasyonu.
2. **Güven sınırı:** upload limiti, JWT şeması, expired web session. Öğren: istemciden gelen her şeyi sınırda doğrulama; authn/authz ayrımı.
3. **Tek konum invariant'ı:** son doğrulama kapısı ve çok şehirli fixture. Öğren: provider adaptörü ile domain kuralı farkı.
4. **Veri tutarlılığı:** Library sync outbox ve idempotency. Öğren: transaction sınırı, eventual consistency ve telafi.
5. **API sözleşmesi:** kalite ve öneri durumlarının ortak fixture'ları; backward compatibility. Öğren: test doubles değil gerçek payload üzerinden contract test.
6. **AI kalite ölçümü:** elle gözden geçirilmiş temsilî set; doğru yer/koordinat, yanlış pini reddetme ve kaynak doğruluğu ayrı metrikler. Beklenen sonuçları mevcut modele uydurma.
7. **Kullanıcı akışı:** iOS gerçek cihaz ve web dar/geniş ekran; paylaşım, izin reddi, oturum yenileme ve erişilebilirlik.
8. **İşletim kanıtı:** izole PostgreSQL'e restore, worker/broker kesintisi, kuyruk gecikmesi, API maliyeti, disk/RAM yükü, alarm testi. Çalışan veritabanına restore yapma.

Her adımın tamamlanması: problem yeniden üretildi → dar değişiklik → regresyon testi → ilgili kalite kapıları → sonuç/limitler belgelendi. Her şeyi aynı anda yeniden yazmak bu yaklaşımın tersidir.

## 6. Mimari bakım planı

`places_service.py` 1000+ satır, `gemini_service.py` yaklaşık 700, web `api.ts` 700+ satır. Satır sayısı tek başına kusur değildir; fakat sağlayıcı HTTP/cache, isim normalizasyonu, aday seçimi, doğrulama ve orkestrasyon farklı değişim sebepleridir. Özellik düzeltildikçe bu sınırlar boyunca küçük modüllere ayrılmalı. Tek dev refactor yerine davranışı koruyan artımlı geçiş yapılmalı.

Migration, geri alma, yedekler ve eski payload uyumu her değişiklikte düşünülmeli. Kaynak kodu test etmek, dağıtılmış sistemin gerçekten çalıştığını kanıtlamaz; ikisine ayrı kanıt gerekir.
