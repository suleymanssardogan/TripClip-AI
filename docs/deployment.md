# Gerçek altyapı dayanıklılık testleri

`./scripts/test-integration.sh` PostgreSQL 15, Redis 7, Qdrant 1.7.4, Toxiproxy ve Python test runner'ı geçici bir Docker Compose projesinde çalıştırır. Aynı servis sürümleri üretim compose dosyasından seçildi. Çıkışta yalnızca kendi projesi temizlenir. Üretim portları, veritabanları, volume'ları veya Docker socket'i test konteynerlerine bağlanmaz. Test veritabanı adı doğrulanmadan temizlik yapılamaz. Docker build context'inde yalnızca gerekli kod ve test dosyaları bulunur.

## Senaryolar

1. Gerçek PostgreSQL bağlantıları aynı video kilidini eşzamanlı alamaz; transaction sona erince başka bağlantı alabilir. PostgreSQL bağlantısı sunucu tarafından sonlandırıldığında da kilit serbest kalır. Video/outbox ekleme hatasında gerçek SQL transaction iki kaydı birlikte geri alır.
2. Gerçek Celery prefork worker, üretim `durable_analysis_task` görevini çalıştırır; video tamamlanır ve tekrar teslim aynı analizi yeniden çalıştırmaz.
3. Toxiproxy Redis bağlantısını keser. Gerçek broker'a gönderim başarısız olur; SQL işi ve video korunur. Bağlantı açılınca iş aynı girdiden tamamlanır.
4. Çalışan Celery worker ve çocukları SIGKILL ile kapatılır. SQL işi processing kalır; yeni worker aktif sahiplik süresini atlayamaz. Süre dolunca yeniden gönderilen iş tamamlanır. Test 900 saniye beklemek yerine SQL tarihini geçmişe alır; üretim sürelerini değiştirmez.
5. Qdrant bağlantısı kesildiğinde gerçek indeksleme işi pending durumuna geri döner. Bağlantı açılıp bekleme süresi dolunca gerçek Qdrant koleksiyonundaki point doğrulanır.

AI/video işlemcisi ve embedding testte deterministik sentetik karşılıklar kullanır. Ücretli AI çağrısı, video indirme veya model ağırlığı indirme yapılmaz. Bu testler model doğruluğu, video kalitesi, ses/OCR başarısı, gerçek maliyet veya üretim yükünü ölçmez. Görev kodu, SQL transaction/lease/claim, Celery, Redis, Qdrant yazımı ve migration'lar gerçektir.

6. API süreci olmadan gerçek bakım servisi SQL işini gönderir, worker analizi tamamlar ve süresi dolmuş ham dosya temizlenir. SIGTERM ile bakım servisi kontrollü kapanır.

## CI ve çıktılar

GitHub Actions `test-integration` işi her main push/PR'da çalışır. Başarısız olursa Docker Build aşaması ilerlemez. JUnit raporu, worker ve servis günlükleri `integration-resilience` artifact'inde saklanır. Yerelde aynı dosyalar `integration-reports/` dizinine yazılır ve Git'e eklenmez.

Docker kapalıysa betik açık hata ile çıkar; entegrasyon testleri geçti sayılmaz. Normal unit test çalıştırmasında bu testler opt-in gerektirdiği için atlanır. Gerçek test için `TRIPCLIP_INTEGRATION=1` yalnızca izole compose runner'ında ayarlanır.

Toxiproxy altyapı servislerini durdurmak yerine TCP erişimini keser. Bu, bağlantı kesintisi deneyidir; Redis veri kaybı, PostgreSQL failover, Qdrant disk bozulması ve dokuz yüz saniyelik gerçek bekleme ayrı kapsamdır.

Referanslar: [Celery worker süreçleri](https://docs.celeryq.dev/en/v5.3.6/userguide/workers.html), [Toxiproxy](https://github.com/Shopify/toxiproxy).
