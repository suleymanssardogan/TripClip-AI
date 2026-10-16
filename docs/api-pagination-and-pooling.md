# Sayfalama ve HTTP havuzları

Kullanıcının video ve gezi listeleri SQL'de sayfalanır. Varsayılan `limit=20`, üst sınır 50, `offset>=0`. Video ve gezi sırası `created_at DESC, id DESC`; aynı zaman damgalı kayıtlar deterministik sıralanır. Gezi sorgusu sahiplik veya collaborator üyeliğini SQL EXISTS ile kontrol eder; aynı gezi iki kez dönmez. Durak sayıları yalnızca o sayfadaki geziler için hesaplanır.

Core API uçları:

- `GET /internal/videos/user/{user_id}?limit=20&offset=0`
- `GET /internal/videos/public?limit=20&offset=0`
- `GET /internal/trips?limit=20&offset=0`

BFF'ler aynı parametreleri iletir. Video listelerinin `plans`, gezi listelerinin `trips` alanları korunur. Ek alanlar `total`, `limit`, `offset`, `has_more` şeklindedir. `total` erişilebilir bütün kayıt sayısı, `has_more` ise sayfa sonundan sonra kayıt olup olmadığıdır. Hatalı parametreler 422 döner. Mobile video listesinde upstream hatası artık sahte boş başarıya dönüşmez.

Web dashboard/gezi listeleri ile iOS Home/gezi listeleri kalan sayfaları “Daha fazla yükle” ile açar. İkinci sayfa hatasında önceki kayıtlar korunur, aynı offset yeniden denenir; tekrar eden kayıt ID'leri eklenmez. iOS eski sunucuda eksik metadata alanlarını kabul eder. Sunucu değişikliği önce dağıtılmalı; eski istemciler yeni sunucuda ilk 20 kaydı gösterir.

Offset sayfalaması eşzamanlı ekleme/silme sırasında snapshot garantisi sağlamaz. Yenileme ilk sayfayı yeniden okur; cursor/snapshot sözleşmesi bu çalışmada yoktur. Şehir filtreli public video araması mevcut 2000 kayıt tarama sınırını korur; buradaki total bütün veritabanının toplamı değildir. Places semantic search hâlâ top-N aramadır; derin sayfalama sözleşmesine dahil değildir. Itinerary geçmiş uçları bu değişikliğe dahil değildir.

Web/Mobile BFF transport havuzları FastAPI lifespan'ında oluşturulup kapatılır. Her istek ayrı AsyncClient, cookie jar ve başlık seti alır; sadece transport paylaşılır. Havuz süreç başına 100 bağlantı, 20 keepalive, 30 saniye keepalive süresi; connect/pool timeout 5 saniye, read/write timeout ilgili route'un bütçesidir. Otomatik retry eklenmez.

Gemini/Ollama/Nominatim/Overpass HTTP çağrıları süreç başına paylaşılan requests HTTPAdapter kullanır. Her çağrı ayrı Session ile çerez/başlık izolasyonu sağlar; adapter fork sonrası yeniden kurulur ve süreç çıkışında kapatılır. Çağrı açık timeout gerektirir; streaming desteklemez. Havuz 10 host/10 keepalive bağlantı tutar; `pool_block=False` olduğundan bu eşzamanlı dış çağrı sayısının kesin üst sınırı değildir. Sağlayıcı throttle ve mevcut Gemini retry/deadline davranışı korunur. OAuth ve APNs adaptörleri bu havuza taşınmadı.

BFF havuz sahipliği/izolasyonu, SQL sayfa sınırları ve yetki kapsamı, geçersiz parametreler, provider pool izolasyonu ve istemci sayfa retry davranışı testlerle kontrol edilir. Gerçek üretim yükü veya keepalive performans artışı ölçülmüş değildir.
