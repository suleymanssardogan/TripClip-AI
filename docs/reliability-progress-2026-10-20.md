# Güvenilirlik çalışması — 20 Ekim 2026

## Uygulanan değişiklikler

- Mobil upload sınırı 100 MB: `limit + 1` kadar okunur; taşma 413 ile Core'a iletilmeden reddedilir. Multipart aktarımının tamamı için proxy/disk sınırları ayrıca önemlidir.
- Mobil JWT: `type=access`, pozitif sayısal subject ve geçerli imza/süre gerekir. Yanlış claim 401 olur, 500'e dönüşmez. Eksik Authorization için mevcut 403 sözleşmesi korunur.
- Web: mevcut ama geçersiz access cookie anonim sayılmaz. Yalnızca refresh cookie kaldığında da 401 dönerek istemcinin mevcut yenileme mekanizması tetiklenir. Hiç oturum yoksa public anonim erişim korunur. Özel kayıtlarda varlık sızdırmayan 404 korunur; genel NOT_FOUND artık doğru 404'e çevrilir.
- Son konum kapısı: NER/OCR/Vision birleştirildikten ve outlier düzeltmeleri yapıldıktan sonra doğrulama tekrar uygulanır. Yer bazında mevcut ilçe/bölge bağlamı korunur. Reddedilen kayıtlar nedenleriyle unresolved listesine gider; rota ve Library girdisine geçmez. Bağlamı olmayan yerde ilçe tahmin edilmez; kontrolün geçmesi kesin doğruluk anlamına gelmez.
- Library: video tamamlanmasıyla aynı transaction'da `library_sync` işi oluşturulur. İlk hızlı senkronizasyon da aynı lease/retry protokolüyle çalışır. Çökme veya hata halinde iş kalır; yeniden çalıştırmada mevcut kullanıcı kaydı tekrar sayılmaz.
- Testler: her pytest süreci geçici ve farklı SQLite dosyası kullanır; uygulama SessionLocal ve fixture aynı URL'yi görür. `tests.conftest` ve `conftest` karışıklığı giderildi. Unit ortamında gerçek analytics aktarımı varsayılan kapalıdır; ilgili testler kendi mock'unu/ayarını kullanabilir.

## Mühendislik gerekçesi

**Güven sınırı:** Dosya/JWT hataları iş mantığına ulaşmadan elenir.

**Invariant:** Konum güvenliği tek bir sağlayıcının iyi davranmasına bağlı kalmaz; tüm analiz yollarından sonra ortak kural uygulanır.

**Atomicity ve eventual consistency:** Video ile senkronizasyon niyeti birlikte commit edilir. Library hemen tamamlanamasa bile yeniden denenecek kayıt kaybolmaz.

**Idempotency:** Aynı işin tekrar gelmesi aynı mekanın kullanıcıya yeniden kaydedilmesine yol açmaz. Bunun hata → retry → tekrar yürütme testi vardır.

**Test izolasyonu:** Bir pytest sürecinin teardown'u başka sürecin tablolarını silemez. Testler geliştiricinin DATABASE_URL'sini kullanmaz.

## Doğrulama sonucu

- Core API tam paket: **893 geçti**, 68.87 saniye.
- Mobile BFF tam paket: **152 geçti**.
- Web BFF tam paket: **124 geçti**.
- Web tam birim paketi: **122 geçti**; sıfır uyarılı lint ve TypeScript kontrolü başarılı.
- `git diff --check` başarılı.

## Entegrasyon sınırları

Docker kapalı tutuldu. Ürün verileri değiştirilmedi, AI sağlayıcısına video gönderilmedi. Yeni job türünü işleyebilmesi için dağıtımda worker ve API aynı sürüme güncellenmelidir. Eski tamamlanmış videolar için geriye dönük Library backfill bu değişiklikte yapılmadı. Kalıcı retry sonrasında da tükenen işler operasyonel izleme gerektirir.

PostgreSQL üzerindeki eşzamanlılık, gerçek broker kesintisi, gerçek ML bağımlılıkları ve tarayıcı/cihaz oturum yenilemesi ayrıca entegrasyon ortamında doğrulanmalı. SQLite/mock testlerinin geçmesi bu kontrollerin yerine geçmez.
