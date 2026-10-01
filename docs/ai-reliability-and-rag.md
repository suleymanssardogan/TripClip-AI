# AI işlerinin toparlanması ve kaynaklı RAG

1 Ekim 2026 uygulama notları. Önceki inceleme: [Mimari değerlendirme](ai-architecture-review.md).

## Uygulanan davranış

- Video sonucuyla aynı SQL transaction'ında `travel_tips` işi kaydedilir.
- Yeni/zenginleşen mekan ve kaynak içeriğiyle aynı transaction'da `place_index` işi kaydedilir. Ağ çağrısı SQL commit öncesinde yapılmaz.
- Core API, 15 saniyelik aralıklarla en fazla 20 işi Celery'ye gönderir. Broker gönderimi için sonuç backend'i kullanılmaz; ilk bağlantı hatasında tur sona erer. Bir API replica'sının arızası başka replica veya yeniden başlatmayla toparlanabilir.
- Dispatcher 60 saniyelik yeniden gönderim aralığını SQL'de atomik olarak sahiplenir. Broker mesajının kaybolması işi silmez.
- Worker işi SQL güncellemesiyle sahiplenir. 900 saniyelik lease, bu görevin 210/240 saniyelik Celery soft/hard limitinden uzundur. Üretimde `prefork` gerekir; `solo` pool hard limit garantisi vermez.
- Aynı işin aktif veya tamamlanmış teslimi atlanır. Worker kaybında lease dolunca yeniden gönderilir. İşlemler en az bir kez teslim edilebilir; indeks upsert'i ve mevcut ipuçlarını atlama davranışı tekrarı güvenli hale getirir. Bu, ana video analizinin eşzamanlı iki ayrı görevini atomik kilitleyen bir sistem değildir.
- İşlem hatasında üstel beklemeyle 8 deneme yapılır. Sonrasında kayıt `failed` olarak operatör müdahalesi için saklanır. `ai_deferred_jobs{status="failed"}` metriği dikkat gerektiren işleri gösterir. Hata alanında kullanıcı içeriği yerine yalnızca hata türü tutulur. Tamamlanmış kayıtlar 7 gün sonra küçük partilerle temizlenir.
- Kaynaklar `PlaceKnowledgeDocument` tablosunda URL, başlık, dil, kaynak türü, içerik hash'i, inceleme ve son geçerlilik tarihiyle saklanır. Import komutu yalnızca operatörün incelendiğini belirttiği resmî/editorial içerikleri kabul eder; LLM üretimi ipuçları kabul edilmez. Bu beyan otomatik bir doğruluk doğrulaması değildir.
- Retriever süresi dolmamış, aday mekan kümesi içindeki kaynakları getirir. Modele kaynak ve tarihleri aktarır. Modelin ürettiği URL'ler kaynak listesine alınmaz. API'nin döndürdüğü `sources`, cevap bağlamına alınmış kaynaklardır; her birinin cevapta gerçekten kullanıldığı iddiası değildir. Web ve iOS bu listeyi "Başvurulan kaynaklar" olarak gösterir.
- Embedding metni mekan adı/şehir/kategoriye ek olarak en fazla 2400 karakter kaynak içeriği içerir. Eski kayıtlar yeniden indeksleme komutuyla güncellenebilir. Kaynaklar SQL'den güncel olarak okunduğundan indeks eskise bile süresi dolmuş kaynak metni modele verilmez.
- Asistanın LLM/araç döngüsünde paylaşılan 45 saniyelik bütçe vardır; HTTP timeout ve retry beklemeleri kalan süreye göre kısalır. Metin üretimi en fazla 2048 çıktı token'ı ister. İpuçları için ayrı 150 saniyelik provider bütçesi vardır ve yalnızca metin sağlayıcısı yüklenir. Bu bütçeler retrieval/model soğuk yükleme süresini veya tek HTTP bağlantısının mutlak toplam süresini garanti eden bir process kill değildir.
- Pipeline'daki isteğe bağlı servis import'ları birbirinden ayrılmıştır. Eksik Whisper/YOLO bağımlılığı diğer servislerin ve Gemini'nin kurulmasını durdurmaz. Temel FFmpeg bağımlılığı hâlâ gereklidir.

## Kurulum ve bakım

Yeni migration `e6b9d18a40c2`, iki tablo ekler. Core API başlangıcındaki mevcut Alembic akışı uygular. Worker yeni kodla yeniden başlatılmalıdır. Canlı sunucuya bu çalışma sırasında dağıtım yapılmadı.

Komutlar `services/core-api` dizininden çalıştırılır:

```sh
venv/bin/python -m app.cli.knowledge import /path/to/reviewed-sources.json --dry-run
venv/bin/python -m app.cli.knowledge import /path/to/reviewed-sources.json
venv/bin/python -m app.cli.knowledge reindex --after-id 0
venv/bin/python -m app.cli.knowledge replay --job-id 123
```

Import dosyası en fazla 500 kayıt içeren bir JSON dizisi olmalıdır. Zorunlu alanlar: `place_id`, `source_url`, `source_title`, `content`, `observed_at`, `expires_at`, `reviewed: true`, `origin: "official"` veya `"editorial"`. `language` varsayılanı `tr`. Tarihler ISO 8601 biçimindedir; UTC'ye çevrilir. Gelecekte inceleme tarihi, geçmişte son geçerlilik tarihi, credential içeren URL, bilinmeyen mekan veya aynı partide tekrarlanan kaynak reddedilir. URL'ye ağ isteği yapılmaz. Aynı mekan/URL yeniden import edildiğinde mevcut içerik güncellenir ve yeni indeks işi oluşturulur. Import işlemi partiyi atomik olarak kaydeder.

Reindex her çağrıda en fazla 500 mekanı kaydeder; komutun döndürdüğü `after-id` ile sonraki partiye geçilir. İlk kez kurulurken mevcut mekanlar bu komutla indekslenmelidir. `replay` yalnızca belirtilen başarısız işi yeniden açar.

## Türkçe değerlendirme

```sh
venv/bin/python -m app.cli.evaluate_retrieval tests/fixtures/turkish_retrieval.json --backend lexical
venv/bin/python -m app.cli.evaluate_retrieval tests/fixtures/turkish_retrieval.json --backend lexical --threshold 0.2
venv/bin/python -m app.cli.evaluate_retrieval tests/fixtures/turkish_retrieval.json --backend embedding --model all-MiniLM-L6-v2
```

`--model` ile farklı embedding modelleri aynı veri üzerinde ölçülebilir. Bu komut üretim koleksiyonunu değiştirmez. Embedding backend'i yerel `sentence-transformers` bağımlılıkları ve model dosyalarının sağlıklı olmasını gerektirir. Yerel ortamda SciPy native modülü yüklenemediği için bu çalışmada embedding modelleri arasında gerçek karşılaştırma yapılmadı.

İlk ölçüm: **8 kurgusal mekan, 14 Türkçe sorgu**, bunların 4'ü bilgi havuzuyla ilgisiz. Fixture üretim verisi veya gerçek kaynak değildir.

| Üçlü karakter tabanlı karşılaştırma | Recall@3 | Precision@3 | MRR@3 | İlgisiz soruya eşleşme |
|---|---:|---:|---:|---:|
| Eşik 0 | 1.00 | 0.37 | 1.00 | 1.00 |
| Eşik 0.2 | 0.80 | 0.70 | 0.80 | 0.00 |

Sonuç bir embedding kalite iddiası değildir: eşik yükseltmenin yanlış eşleşmeyi azaltırken doğru eşleşmeyi de kaybettirebileceğini gösterir. **Üretim modeli ve skor eşiği değiştirilmedi.** Sonraki ölçüm, gerçek ve anonimleştirilmiş gezi sorgularıyla etiketli veri, çok dilli model karşılaştırması ve kaynak dayanağı kontrolünü içermeli. Model değişimi ayrı, sürümlü Qdrant koleksiyonu ve yeniden indeksleme gerektirir.

## Henüz tamamlanmayanlar

Gerçek kaynak seçimi/incelemesi ve içeriğin import edilmesi, canlı Qdrant/broker kesinti testi, gerçek video doğruluk/maliyet ölçümü, ana analizin atomik claim mekanizması ve ThreadPool aşamalarına gerçek process izolasyonu gerekir. Bu çalışma bunların tamamını üretimde doğrulandığını iddia etmez. Özellikle `Future.result(timeout=...)` çalışan thread'i durdurmaz; pipeline'ın genel süre garantisi ayrıca ele alınmalıdır.

## Doğrulama sonucu

- İlgili backend suite: **258 test geçti**; broker hatası, lease/tekrar teslim, backoff, model bağımlılık izolasyonu, kaynak geçerliliği, cevapta kaynak listesi ve migration upgrade/downgrade dahil.
- Web asistanı: **12 test geçti**; kaynak bağlantısı ve inceleme tarihi dahil. TypeScript kontrolü temiz.
- iOS asistanı: **17 test geçti**; eski yanıtta kaynak alanının olmamasıyla uyum dahil. iOS derlemesi başarılı.
- İki sözlüksel değerlendirme koşusu tamamlandı; embedding/model kıyaslaması ve canlı dış servis testleri yapılmadı. Gerçek kaynak havuzuna bu çalışma sırasında içerik eklenmedi.

## 1 Ekim 2026 ek kontroller

Upload ve URL analizleri PostgreSQL transaction advisory lock ile video başına seri çalışır. Kilit başka işteyse görev 30 saniye sonra tekrar denenir; kilit süreç bağlantısı kapanınca serbest kalır. Upload görevine de URL görevindeki 720/780 saniye soft/hard sınırları eklendi. Bu, prefork worker işlemini sonlandırır; tekil thread aşamalarını ayrı süreçlere dönüştürmez.

KVKK teknik kontrolleri, ham dosya saklama/imha işleri ve üretimde sağlayıcı inceleme kapıları için [kvkk-controls.md](kvkk-controls.md). Gerçek kaynakların incelenmesi/importu, gerçek video doğruluk/maliyet ölçümleri ve embedding karşılaştırması için doğrulanmış veri kümesi hâlâ gerekir. Docker daemon erişilebilir olmadığından gerçek broker/Qdrant/Postgres arıza deneyleri tamamlandı olarak işaretlenmemiştir.

## Ana video analizi için kalıcı iş akışı

Dosya yükleme ve URL paylaşımı `SqlVideoRepository.create` içinde video ile `video_analysis` işini aynı SQL commit'inde oluşturur. URL ve kaynak adı videoda tutulur; broker mesajı yalnızca iş ID'sini taşır. Başarılı analizde URL temizlenir. API başarılı kayıt ardından gönderimi arka planda tetikler; broker arızasında video silinmez. Mevcut 15 saniyelik dispatcher gönderimi tekrar dener; API yeniden açıldığında da pending işler okunur.

Ana işler `durable_analysis_task` üzerinden çalışır: 720/780 saniye soft/hard süre, 900 saniye SQL sahiplik süresi, en fazla sekiz deneme ve 30–3600 saniye artan bekleme. Worker kaybında broker'ın sınırsız anında yeniden teslimi yerine SQL sahiplik süresinin dolmasıyla yeniden gönderilir. Son denemede worker kaybı da SQL video durumuna `failed` olarak yansıtılır. Eski `process_video_task` ve `process_url_task` mesajları desteklenir ve aynı video kilidini kullanır.

Kuyrukta bekleyen veya geçici hatadan sonra tekrar sıra bekleyen video `queued` görünür; sırf yükleme yaşı geçtiği için başarısız sayılmaz. Silinen veya tamamlanmış video yeniden analiz edilmez. Yan ipucu işleri kısa worker görevinde, ana analiz işleri uzun worker görevinde yürütülür.

Veritabanı ile yerel dosya sistemi tek transaction değildir. SQL commit sonucunun bağlantı kopması nedeniyle belirsiz olduğu durumda dosya hemen silinmez: iş aslında commit edilmiş olabilir. Gerçek rollback sonrası kalan sahipsiz dosyalar için ayrı staging/orphan temizliği ileride gerekir. Yeni outbox akışı dağıtımdan önce oluşmuş, URL girdisi saklanmamış eski işlerin bağlantısını yeniden oluşturamaz; bunlar operatör incelemesi gerektirir.

Doğrulama: video/outbox rollback, broker arızası ve tekrar yayınlama, URL girdisinin kalıcılığı, upload/URL worker seçimi, tekrar teslim, geçici hata/backoff, son denemede worker kaybı, üretimde kuyruk arızasına rağmen upload kabulü ve migration ileri/geri testleri. Gerçek PostgreSQL/Redis/Celery süreç kaybı deneyi Docker daemon olmadığı için ayrıca staging'de yapılmalı.

## Gerçek altyapı test paketi

PostgreSQL/Redis/Celery/Qdrant için izole Compose test ortamı ve CI işi eklendi. Senaryolar, sentetik AI sınırı ve çalıştırma talimatları: [integration-tests.md](integration-tests.md). Test paketinin oluşturulması gerçek arıza deneylerinin geçtiği anlamına gelmez; sonuçlar CI JUnit raporundan doğrulanmalıdır.
