# RAG ve video doğruluk değerlendirmesi

Bu araçlar offline çalışır; üretim veritabanını değiştirmez, model/sağlayıcı çağırmaz. Sentetik fixture yalnızca ölçüm kodunun doğrulanması içindir. Gerçek veri kümesi henüz depoda bulunmuyor; gerçek doğruluk sonucu elde edilmiş değildir.

Komutları `services/core-api` dizininden çalıştırın:

```sh
venv/bin/python -m app.cli.evaluate_retrieval tests/fixtures/turkish_retrieval.json --threshold .2 --output /tmp/retrieval-report.json
venv/bin/python -m app.cli.evaluate_videos /path/video-gold.json /path/video-predictions.json --output /tmp/video-report.json
```

Her veri kümesi açıkça `synthetic` boolean alanı taşımalıdır. Gerçek veri için `synthetic:false` ve `provenance` içinde `reviewed:true`, `authorized:true`, `anonymized:true`, ayrıca boş olmayan `source` gerekir. Bunlar veri hazırlayanın beyanıdır; otomatik anonimleştirme veya hukuki uygunluk doğrulaması değildir. Ham video, kişi görüntüsü, konuşma, kullanıcı kimliği, özel bağlantı veya anahtarları depoya/rapora koymayın. Sorgu metinleri retrieval raporunda bulunur; veri kümesine yalnızca anonimleştirilmiş sorgular alın.

Video gold formatı:

```json
{"synthetic":false,"provenance":{"reviewed":true,"authorized":true,"anonymized":true,"source":"izinli gezi korpusu v1"},"videos":[{"id":"video-001","location_ids":["place-001","place-002"]}]}
```

Kaydedilmiş tahmin formatı:

```json
[{"id":"video-001","location_ids":["place-001"],"duration_s":12.5}]
```

`location_ids` insan tarafından doğrulanmış ortak yer kimlikleridir. Pipeline'ın `deduplicated_locations` çıktısı değerlendirme için aynı kimliklerle eşleştirilmelidir; bilinmeyen yerler ayrı kimlik taşımalı ve yanlış pozitif sayılmalıdır. İsim benzerliğinden otomatik doğru eşleşme varsayılmaz. Her gold video için tam bir tahmin kaydı gerekir; çıktı üretilemeyen analiz boş yer listesiyle kaydedilir. Fazladan/eksik video, yinelenen kimlik, geçersiz süre reddedilir.

Video raporu mikro precision/recall/F1, tam eşleşme oranı, yanlış pozitif/negatif sayısı ve mevcut sürelerin ortalamasını verir. Gold ve tahminlerin ikisi de boşsa precision/recall/F1 null olur; tam eşleşme yine doğrudur. Rapor koordinat, OCR/transkript doğruluğu veya cevap dayanağı ölçtüğünü iddia etmez.

RAG formatı mevcut fixture ile aynıdır: `documents` (id, name, city/category/content), `queries` (text, relevant_ids). Gerçek belgeler için kaynak ve inceleme bilgilerini veri kümesi provenance alanında koruyun. Sözlüksel baseline üretim Qdrant yolunun veya cevap üretiminin değerlendirmesi değildir. Embedding seçeneği yerel modeli çağırır ve indirme gerektirebilir; ayrıca çalıştırılmalıdır. Eşikleri geliştirme kümesinde seçip bağımsız test kümesinde ölçün; test etiketlerini eşik ayarlamak için kullanmayın.

Raporlar veri kümesi SHA-256 kimliğini; video raporu ayrıca tahmin dosyası SHA-256 kimliğini taşır. Aynı sabit veriyle model sürümlerini kıyaslayın. Temsil gücü olan, farklı şehir/dil/video kalitesi ve negatif örnekler içeren izinli bir korpus sağlanmadan üretim doğruluğu için kabul eşiği belirlemeyin.
