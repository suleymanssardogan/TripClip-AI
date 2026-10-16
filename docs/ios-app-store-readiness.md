# iOS App Store hazırlığı

3 Ekim 2026. Bu belge mağaza onayı verildiği veya uygulamanın gönderime hazır olduğu anlamına gelmez. Apple'ın güncel [App Review Guidelines](https://developer.apple.com/app-store/review/guidelines/), [hesap silme rehberi](https://developer.apple.com/support/offering-account-deletion-in-your-app), [App Privacy Details](https://developer.apple.com/app-store/app-privacy-details/) ve [required-reason API açıklamaları](https://developer.apple.com/documentation/bundleresources/app-privacy-configuration/nsprivacyaccessedapitypes/nsprivacyaccessedapitype) esas alındı.

## Uygulanan ilk hazırlık

- Video yüklemeden önce AI paylaşımını açıklayan ayrı izin ekranı; izin verilmeden veri yüklenmez. Gezi asistanındaki normal/suggested/retry gönderimleri aynı izin kontrolünden geçer.
- Share Extension aynı hesaba ait izni kullanır; izin yoksa gönderimden önce açıklama/onay ister. BackgroundUploader, enqueue sırasında da izni kontrol eder.
- İzin hesap ID'si, API adresi, sağlayıcı adı ve açıklama sürümüne bağlıdır; değişiklik yeniden izin gerektirir. İzin cihazda/App Group'ta tutulur; merkezi, hukuki rıza kayıt sistemi değildir.
- Ana sayfa hesap menüsünde “Gizlilik ve veri paylaşımı”: izin geri alma, gizlilik/kullanım koşulları bağlantıları, AI sonuçlarının doğrulanması açıklaması. İzin geri alma başlamış işleri iptal etmez veya önceki verileri silmez.
- Main app ve extension manifestlerinde App Group UserDefaults gerekçesi `1C8F.1`; main app'te local UserDefaults için ayrıca `CA92.1`. Video/ses/kullanıcı içeriği, hesap kimlikleri ve uygulamanın kullandığı diğer veri kategorileri beyan edildi. Manifest App Store Connect formunu otomatik doldurmaz.
- Sign in with Apple entitlement ve yapılandırmaya bağlı APNs ortamı proje kaynağında korunur. Apple Developer portal/provisioning doğrulaması yapılmadı.
- Yerel geliştirme bağlantısı için LAN kullanım açıklaması her iki target'ta bulunur. Geniş ATS HTTP izni eklenmedi.
- 100 MB video sınırı istemcide multipart kopyası oluşturulmadan kontrol edilir. PhotosPicker yine veriyi önce belleğe alır; büyük video için dosya tabanlı transfer sonraki performans çalışmasıdır. Upload URLSession işlem sonunda kapatılır.
- Başarılı hesap silme session epoch'u artırır; devam eden refresh sonucu silinmiş hesabı geri yükleyemez. Logout/silme cihazdaki AI izin ve bekleyen paylaşım metadata'sını temizler.

`AI_PROVIDER_NAME` build setting'i varsayılan `Google Gemini`dir. Hem ana app hem extension Info.plist'e aktarılır. Bu değer **gerçekte kullanılan tüm AI alıcılarıyla uyumlu** olmalı; Gemini/Ollama veya başka sağlayıcıya geçerken açıklama ve gizlilik politikası güncellenmeli, açıklama içeriği değişirse `AIConsentStore.signature` sürümü artırılmalıdır. Build metadata backend'in provider konfigürasyonunu otomatik keşfetmez. Web'deki AI veri paylaşımı bu iOS çalışmasının kapsamında değildir.

## Gönderim öncesi hâlâ gerekenler

1. **Apple hesabı silme doğrulaması:** Authorization code exchange, şifreli refresh token saklama ve hesap silmeyle aynı transaction içinde revocation kuyruğu eklendi. Maintenance iptal isteğini tekrar dener ve başarılı yanıt sonrası belirteci siler. Apple Developer bilgileriyle gerçek cihaz/provider testi hâlâ gerekli; yapılandırma ve eski hesap istisnası [Apple yaşam döngüsü](apple-sign-in-lifecycle.md) belgesindedir.
2. **Dış kaynak videoları:** Instagram vb. URL indirme/import özelliği için kaynak servislerin yetkilendirmesi ve kullanım koşulları doğrulanmalı (5.2.2/5.2.3). Kullanıcının kendi videosu olması kaynak servis iznini otomatik sağlamaz. Yetki yoksa bu özellik mağazaya gönderilecek ürün kapsamından çıkarılmalı; incelemeciye gizlenmemeli.
3. **Gerçek altyapı:** Release `https://api.tripclip.app` kullanır. Bu endpoint, web gizlilik/kullanım koşulları sayfaları ve destek iletişimi gerçekten yayımlanmış ve erişilebilir olmalı. Yerel Docker incelemecinin ulaşacağı backend değildir. İnceleme süresince servisler açık, kota yeterli olmalı.
4. **App Privacy:** Manifestteki beyanlar ile App Store Connect'in veri/amaç/bağlantı formunu ve sağlayıcı veri envanterini karşılaştırın. Analytics açıksa ürün etkileşimleri beyan edilmeli; kapatılırsa manifestteki kategori de gerçek release davranışına göre daraltılmalı. Video/ses içinden çıkarılan kişi/konum bilgisinin kapsamı ayrıca incelenmeli.
5. **İmzalı gerçek cihaz:** Main/Share App Groups, Sign in with Apple, push entitlements ve provisioning profilleri Apple Developer portalında etkin olmalı. Gerçek cihazda Apple giriş, hesap silme, paylaşım uzantısı, uygulama kapalıyken upload/push, offline/retry ve izin reddi denenmeli. Unsigned simulator build bunları doğrulamaz.
6. **Ürün kalitesi:** Küçük ekran, en büyük Dynamic Type, VoiceOver, koyu tema, uzun Türkçe yer adları, boş/başarısız analiz ve ağ kopması akışlarını doğrulayın. Üçüncü taraf görsel lisanslarını ve public içerik varsa raporlama/moderasyon ihtiyaçlarını ayrıca tamamlayın.
7. **Store metadata:** Gerçek ekran görüntüleri, yaş derecesi, açıklama/destek URL'si, inceleme hesabı ve örnek video hazırlayın. İnceleme hesabı/şifresi depoya konulmaz. İnceleme notlarında asenkron analiz, AI veri paylaşımı, izin iptali, hesap silme yolu ve mevcut dış kaynak özellikleri dürüstçe anlatılır.

## Yerel kontrol

```sh
python3 scripts/check-ios-readiness.py
```

Bu araç manifest gerekçesi/kaynak üyeliği, entitlement, ATS, LAN açıklaması ve 1024px opak ikon için offline paket kontrolüdür. Archive signing, API erişimi, hukuki inceleme, Apple portal veya App Review değerlendirmesi değildir.

3 Ekim güncel kontrol sonucu: Xcode lisans engeli kalktı. Xcode 27.0 ile uygulama ve Share Extension derlendi; yerel imzalı iPhone 17 Pro/iOS 26.2 simülatöründe AIConsentStore, AuthEnvironment, APIClient, TripAssistantViewModel, HomeViewModel, OptimizerRouteCalculator ve OptimizerRouteCache testlerinde **96 test, 0 hata**. Yeni derleyicinin rota sağlayıcısında bulduğu actor sınırı hatası `OptimizerRoutingProviding` main actor izolasyonuyla giderildi. Keychain erişimi gereken testler `CODE_SIGNING_ALLOWED=YES CODE_SIGN_IDENTITY=-` ile çalıştırıldı; imzasız koşu bu erişimi doğrulayamaz. Offline paket kontrolü ve development Compose config kontrolü de geçti. Gerçek cihaz provisioning, dış servisler ve App Review doğrulanmış değildir.
