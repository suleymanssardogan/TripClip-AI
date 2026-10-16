# Xcode ve Docker ile yerel iOS testi

Önce Docker Desktop'ı açın ve Docker engine hazır olana kadar bekleyin. 3 Ekim canlı kontrolde dokuz development Compose servisi başlatıldı; core-api/mobile-bff ve PostgreSQL/Redis readiness başarılı. Xcode'u da açıp ilk kurulum adımlarını tamamlayın. 3 Ekim son kontrolünde lisans engeli kalktı; Xcode 27.0 ile derleme ve 96 ilgili simülatör testi başarılı oldu. Keychain testlerini imzasız çalıştırmayın; simülatörde yerel imza, fiziksel cihazda uygun provisioning gerekir.

Depo kökünde `.env` yoksa `.env.example` kopyasını oluşturun. Anahtarları burada özel olarak doldurun; `.env` depoya girmez. Gemini ile gerçek analiz için geçerli `GEMINI_API_KEY` gerekir. `JWT_SECRET_KEY` ve `INTERNAL_API_SECRET` aynı `.env` üzerinden core, worker, maintenance ve BFF'lere aktarılır; üretimde güçlü ve varsayılan olmayan değerler kullanılır.

```sh
docker compose up --build -d
docker compose ps
```

İlk build ML bağımlılıklarını/model ağırlıklarını indirebilir; süre ağ ve makineye bağlıdır. Web Next.js uygulaması development Compose'da yoktur; iOS testi için gerekli değildir. `celery-worker` ve `maintenance` servisleri açık olmalı; maintenance SQL kuyruğundaki analizi worker'a gönderir.

```sh
curl http://localhost:8001/health
curl http://localhost:8000/health
```

`ios/TripClipApp.xcodeproj` dosyasını Xcode'da açın. `TripClipApp` scheme, Debug ve iPhone Simulator seçin. Simülatör otomatik `http://localhost:8001` kullanır. Fiziksel iPhone için Mac ve telefon aynı Wi-Fi'de olmalı; Xcode Debug build setting'indeki `DEV_API_HOST` değerini Mac'in güncel LAN IP'siyle değiştirin. Depodaki `192.168.1.103` örneği güncel IP'niz olmayabilir. Yerel ağ iznini verin; reddedildiyse iOS Ayarlar'dan yeniden açın. App Group/Apple/push için gerçek cihaz signing hesabınızın yetkileri gerekir.

1. E-posta ile üye olun; Docker loglarında sürekli 401 veya bağlantı hatası olmadığını kontrol edin.
2. Kullanım izni olan, kısa ve 100 MB altında bir gezi videosu seçin.
3. AI paylaşım açıklamasında önce “Şimdi değil” seçin; upload başlamamalı. Tekrar seçip izin verin, analizi başlatın.
4. Kuyruk → ilerleme → sonuç akışını, mekanları ve haritayı kontrol edin. Sonuçta sıfır yer varsa bunu başarı/doğruluk göstergesi saymayın; video gezi içeriği olmayabilir veya bir çıkarıcı fallback kullanmış olabilir.
5. Gizlilik menüsünden izni geri alın; yeni upload/asistan mesajı tekrar izin istemeli. Kayıtlı geziler okunabilmeli.
6. Sunucuyu kapatıp tekrar açarak hata/retry deneyimini kontrol edin. Silme testi için ayrı test hesabı oluşturun; hesap silme verileri kalıcı kaldırır.

```sh
docker compose logs --tail=100 core-api celery-worker maintenance mobile-bff
```

Log veya `.env` dosyası paylaşırken anahtar, token, kişisel içerik ve özel bağlantıları paylaşmayın. Gerçek cihaz Share Extension/push akışı ayrıca denenmelidir; simülatör bu davranışlar için son doğrulama değildir.

## 3 Ekim yerel uçtan uca kontrolü

Gerçek Docker PostgreSQL/Redis/Celery/maintenance/mobile-bff üzerinde ayrı geçici hesapla kayıt ve giriş 200, sentetik 5 saniyelik video upload 200, SQL kuyruğundan analiz `completed`, plan/gezi listeleri 200, hesap silme 200 ve silinen hesabın eski oturumuyla gezi listesi 401 doğrulandı. Yalnız oluşturulan geçici hesaplar temizlendi; mevcut kullanıcı hesapları silinmedi.

Canlı denemede yakalanıp düzeltildi:
- Gemini boş mekan listesi döndürdüğünde `regions` tanımlanmadan kullanılıyordu; boş/provider-fallback sonuçlarında analiz artık tamamlanır. İki regresyon senaryosu eklendi.
- Hesap silindikten sonra süresi dolmamış JWT subject'i bazı listelerde kabul ediliyordu; internal kullanıcı header'ı için aktif SQL hesap kontrolü eklendi. Silinen/devre dışı hesap 401 alır.

Sentetik video mekan içermediğinden sıfır mekan beklenir; bu deneme mekan çıkarma doğruluğunu, gezi oluşturmayı veya iOS ekranlarını baştan sona doğrulamaz. Kullanıcı videosu sağlayıcıya gönderilmeden ayrı açık izin gerekir. API testleri iOS'un kullandığı mobile-bff üzerinden çalıştırıldı; fiziksel cihaz/UI testi ayrıca gereklidir.

## 3 Ekim gerçek Antalya videosu denemesi

Kullanıcı, `tripcli-ai-videos/antalya-gezilecek-yerler.mp4` dosyasının Google Gemini ile analizine açık izin verdi. Yaklaşık 32 saniye/16 MB video, gerçek development Docker ortamında mobile-bff üzerinden ayrı geçici hesapla işlendi. Analiz 140,79 saniyede tamamlandı. Kayıt, giriş, upload, mekan kütüphanesi, gezi oluşturma, gezi detayı, plan/gezi listeleri ve hesap silme 200; silinen hesabın eski access token'ıyla liste isteği 401 aldı. Oluşturulan test hesabı ve ona ait video/gezi kayıtları silindi; kullanıcının kaynak video dosyasına dokunulmadı.

17 sonuç ve 17 gezi durağı üretildi. Bunların 10'u coğrafi veritabanında eşleşti (`exact` etiketi gerçek dünyada bağımsız doğruluk onayı değildir), 7'si `approximate` olarak aynı Antalya şehir merkezi koordinatına düştü. Videonun ekran yazılarında Patara plajı görünürken ayrıca Patara Antik Kenti çıkarıldı; bu ek adayın açık görsel kanıtı bulunamadı. Video 16 yer sunuyor. Bu örnek mekan doğruluğu veya rota kalitesi açısından başarılı sayılmamalı.

Sonraki kalite işi: çıkarılan adların video/OCR/transkript kanıtını korumak; desteklenmeyen ek adayları engellemek; çözülmeyen mekanları şehir merkezine pinleyip rota durağı olarak kullanmamak; approximate bilgisini kütüphane/gezi modellerine taşımak. Overpass zaman aşımları ve Nominatim fallback süresi de performansı etkiledi. Benchmark gold label'ları değiştirilmedi.

Bu çalışma API/worker/veritabanı uçtan uca kontrolüdür. iOS gerçek ekran gezintisi/PhotosPicker/AI izin ekranı/harita render/gerçek cihaz doğrulaması yapılmış sayılmaz; ekran erişim aracı yanıt vermedi.

## Aynı hesabın web tarafındaki sonucu

Kullanıcının hesabı silmeme isteği üzerine tekrar analiz ayrı `webcheck_*` hesabında yapıldı; hesabı/video/geziyi koruyoruz. Yeni video ID 48, analiz 25,85 saniye (önceki analiz/geocoding önbellekleri kullanıldı), 17 mekan ve 17 gezi durağı. Aynı hesabın web giriş formuyla giriş yapıldı; `/dashboard` kartı ve `/analyze/48` detay sayfası tarayıcıda doğrulandı. Özel hesabın şifresi ve tokenları bu belgede/depo içinde tutulmaz.

Web testinde düzeltilenler: detay GET istekleri core-api'ye doğrulanmış oturum subject'ini iletmiyordu; artık optional cookie/Bearer kimliği owner kontrolüne aktarılıyor, anonim kullanıcı için kimlik üretilmiyor ve özel sonuçlar herkese açılmıyor. Web API plan kartı alanlarını camelCase döndürürken frontend snake_case okuduğu için mekan sayısı 0 görünüyordu; liste yanıtları frontend'in mevcut modele normalize ediliyor. Dashboard artık 17 mekan gösteriyor. İlgili web-bff 19 ve web API 6 testi geçti, TypeScript kontrolü geçti.

MapPreview'ın eski CARTO katmanı API key required görseli döndürdü; standart OpenStreetMap tile URL ve doğru attribution ile değiştirildi. Tarayıcının normal Referer/User-Agent/cache davranışı korunur; offline/prefetch özelliği eklenmedi. Üretim sağlayıcı kapasitesi ve koşulları [OSM tile policy](https://operations.osmfoundation.org/policies/tiles/) doğrultusunda değerlendirilmelidir.

Sonuçların kalite sınırlamaları (7 yaklaşık şehir merkezi, kanıtsız Patara Antik Kenti adayı) devam ediyor. Webde görünmesi bu sonuçların doğruluğunu veya rota güvenilirliğini onaylamaz.
