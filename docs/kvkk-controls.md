# KVKK teknik ve işletme kuralları

1 Ekim 2026. Bu belge uyumluluk sertifikası değildir. Veri sorumlusu kimliği, faaliyet bazında işleme şartı, alıcılar ve ülke bilgileri işletme tarafından tamamlanmalıdır. Üretime dağıtım bu çalışma kapsamında yapılmadı.

## Uygulanan kontroller

- Eski ve yeni video analizleri varsayılan özel. Keşfet ve şehir filtresi yalnızca `is_public=true` kayıtları döndürür. Özel tamamlanmış analizler de sahibinden başkasına 404 verir. Açık analizlerde dosya adı, ham OCR, transkripsiyon, ham NER ve OCR POI içeriği gösterilmez. Gezi paylaşım/davet mekanizması ayrı yetkilendirme kullanır. Yayınlama için kullanıcı arayüzü eklenmedi; SQL üzerinde otomatik yayınlama yapılmamalıdır.
- Üretimde Gemini, Ollama, Google Vision, Nominatim ve Overpass çağrıları `PRIVACY_REVIEWED_PROVIDERS` içinde sağlayıcı adı bulunmadan ağ isteği yapamaz. Ollama yerel kurulsa dahi altyapı konumu/veri işleme incelemesi gerekir. Bu ayar bir açık rıza veya hukuki aktarım mekanizması değildir; yalnızca işletme incelemesi kapısıdır.
- Üç API servisinde Sentry varsayılan kişisel veri ve yerel değişken toplamayı kapatır; kullanıcı, istek, breadcrumbs, ek bağlam, etiketler, hata mesajı ve log metni ihracattan çıkarılır. Sentry ayrıca sağlayıcı inceleme listesinde bulunmadan açılmaz. İz/tracing varsayılan sıfırdır. Operatör tracing oranını artırmadan ayrıca incelemelidir.
- Mongo kullanım analitiği varsayılan kapalı. Üretim kontrolü analitik açıkken dağıtımı reddeder; amaç, süre ve eski kullanıcı olaylarının silinmesi tamamlanmadan açılmamalıdır. Önceden toplanmış Mongo olayları otomatik silinmiş sayılmaz.
- Ham dosyalar yükleme yaşına göre temizlenir: tamamlanmış analiz 24 saat, başarısız analiz 168 saat. Çalışan/yüklenmiş işler hariçtir. Plan/analiz çıktıları kullanıcı silene kadar saklanır. Süreler `RAW_UPLOAD_RETENTION_HOURS` / `FAILED_UPLOAD_RETENTION_HOURS` ile 1–720 saat arasında ayarlanır; değişiklik aydınlatma metnine de yansıtılmalıdır.
- Temizlik bağımsız `maintenance` servisinde 15 dakikada bir, sınırlı partilerle çalışır. API yeniden başlatılması bu döngüyü durdurmaz. Yalnızca `UPLOAD_DIR` altındaki dosyaları silebilir. Servis durmuşsa işlem sonraki açılışta sürer. Sürekli dosya silme hataları operasyonel inceleme gerektirir.
- Video/hesap SQL silme işleminde dosya imha işi aynı işlemde kalıcı yazılır. İlk dosya silme denemesi başarısız olsa veya süreç kapanmış olsa temizlik yeniden dener. Tamamlanan işler silinir; sıradaki işlerde yalnızca dosya yolu ve tarih tutulur.
- SQL silme ve ham dosya imha kayıtları ayrı tutulur; kullanıcı kimliği, e-posta veya dosya yolu içermez. En az üç takvim yılı korunur. Hesap SQL silme kaydı dış sağlayıcılardaki bütün verilerin imha edildiği anlamına gelmez.

## Yayın öncesi işletme tarafından tamamlanması zorunlu işler

1. Veri sorumlusu unvanı, adresi, başvuru kanalı; işleme envanterinde her veri/amaç için somut hukuki şart. `LEGAL_CONTENT_APPROVED` ancak bu incelemeden sonra açılır. Aydınlatma ile açık rıza ayrı süreçlerdir; genel bir KVKK onay kutusu bütün işlemler için dayanak yapılamaz.
2. Barındırma, AI, Google/Apple giriş, APNs, e-posta, Sentry, harita ve indirme hizmetleri için alıcı, ülke, alt işleyen, veri türü, süre ve sözleşme envanteri. Runtime kapıları listelenen AI/konum/Sentry servisleri içindir; tüm internet çıkışlarını engelleyen bir ağ politikası değildir.
3. Yurt dışı aktarımı için güncel madde 9 rejimine uygun güvenceyi belirlemek ve gerekli sözleşme/bildirimleri tamamlamak. Düzenli aktarımı genel bir rıza kutusuyla meşrulaştırmayın. `PRIVACY_REVIEWED_PROVIDERS` yalnızca belgeli kararın ardından doldurulur.
4. Yedek erişimi ve şifreleme, güvenlik günlüklerinin sınırlı süresi, silme taleplerinin yedek geri yükleme sonrası yeniden uygulanması. Mevcut yedek betiğinin varsayılanı 14 gündür; bu tek başına silinen hesabın geri gelmesini engellemez. Geri yüklenen ortam bu kontrol tamamlanmadan kullanıcı trafiğine açılmamalıdır.
5. İlgili kişi başvurularında kimliği ölçülü doğrulama, talebi kayıt altına alma, uygulanacak yasal sürede yanıt ve alıcılara bildirim prosedürü. Yeni kimlik belgesi kopyalarını rutin olarak toplamayın.
6. VERBİS yükümlülüğü/istisnası, üçüncü kişileri içeren video yüklemeleri, çocuk kullanıcılar, ihlal müdahalesi ve yetkili erişim incelemesi. Kurumsal bilgiler bilinmediğinden sonuç varsayılmadı.

## Resmî dayanaklar

- [Aydınlatma Tebliği](https://www.kvkk.gov.tr/Icerik/4132/aydinlatma-yukumlulugunun-yerine-getirilmesinde-uyulacak-usul-ve-esaslar-hakkinda-teblig): aydınlatma ve rıza ayrı; belirli amaç ve hukuki şart açıklanır.
- [Güncel yurt dışı aktarım rejimi](https://www.kvkk.gov.tr/Icerik/2053/Yurtdisina-Aktarim): yeterlilik/uygun güvence/istisnai hâller ayrımı.
- [İmha Yönetmeliği](https://www.kvkk.gov.tr/Icerik/5441/KISISEL-VERILERIN-SILINMESI-YOK-EDILMESI-VEYA-ANONIM-HALE-GETIRILMESI-HAKKINDA-YONETMELIK): işlem kayıtlarını en az üç yıl saklama.

## Doğrulama sınırları

SQLite geçişi ve erişim/imha/sağlayıcı engeli testleri otomatik yapılır. PostgreSQL kilidi bağlantı üzerinde transaction advisory lock kullanır; upload ve URL görevleri aynı kilidi alır, başka iş varsa 30 saniye sonra tekrar dener. Worker kapanınca bağlantı kilidi serbest kalır. SQLite yerel test modu bu kilidi uygulamaz. Celery prefork görevlerinin soft/hard sınırları 720/780 saniyedir; thread bazındaki aşama timeout'larının tek tek thread'i öldürdüğü iddia edilmez. PostgreSQL/Celery gerçek süreç kaybı ve bağlantı kopması deneyleri Docker daemon olmadığı için bu ortamda doğrulanamadı.
