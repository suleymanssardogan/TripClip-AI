# TripClip tasarım dili

Web ve iOS aynı sade, açık ve ferah görsel dili kullanır. Web renkleri `web/src/app/globals.css`, iOS renkleri `ios/TripClipApp/Core/DesignSystem/AppColors.swift` dosyasındaki anlamsal token'lardan gelir.

| Rol | Açık tema | Kullanım |
| --- | --- | --- |
| Zemin | `#F8FAFC` | Sayfa arka planı |
| Yüzey | `#FFFFFF` | Kart ve alanlar |
| Metin | `#182531` | Başlık ve ana içerik |
| Vurgu | `#1A67B9` | Birincil eylem ve bağlantı |
| Rota | `#1C707D` | Konum ve yardımcı vurgu |

Ekranlarda illüstrasyon, dekoratif harita, emoji ve büyük simge blokları kullanılmaz. İçerik net başlık, kısa açıklama, ince sınır ve yeterli boşlukla düzenlenir. Düğmeler ve kartlar orta derecede yuvarlatılmıştır. Gerçek veriye benzemesi olası örnekler açıkça “Örnek arayüz” olarak etiketlenir.

Web'in seyahat fotoğrafı `web/public/images/istanbul-editorial.webp` dosyasındadır. Yapay olarak üretilmiş bu görsel, İstanbul'un birebir belgesel fotoğrafı olarak sunulmaz; göründüğü yerde “Temsili görsel” açıklaması kullanılır. Fotoğraf yalnızca editoryal alanlarda yer alır; gezi kartlarında gerçek içerik varmış gibi kullanılmaz.

Marka işareti gezinmede `tripclip.` kelimesidir. Uygulama simgesi, `web/src/app/icon.svg` içindeki tek renkli küçük `t` harfinden üretilir; iOS AppIcon aynı vektörün 1024 × 1024 PNG çıktısıdır. İkisi birlikte güncellenmelidir.

Web varsayılan olarak açık temada açılır ve kullanıcı isterse koyu temayı seçebilir. iOS sistem temasını izler. Her iki temada metin ve eylem kontrastı korunmalıdır.
