# Apple giriş ve hesap silme yaşam döngüsü

3 Ekim 2026. iOS authorizationCode + identityToken gönderir; mobile/web BFF bu alanları core-api'ye aktarır. Kod zorunludur: eski istemcinin yalnız identity token gönderdiği istek 422 alır. Web'de Apple giriş UI'si bu çalışmayla eklenmedi. Sunucu imzalı token'ın issuer/audience/expiry/subject alanlarını doğrular, kodu Apple token endpoint'inde değiştirir ve dönen identity token'ın subject alanını karşılaştırır. Sonrasında Apple refresh token bağımsız Fernet anahtarıyla şifrelenir. Private key/client secret/Apple refresh token istemciye dönmez.

## Yapılandırma

Core-api ve maintenance için aynı `APPLE_CLIENT_ID` (native bundle ID: `com.sardogan.TripClipAI`), `APPLE_TEAM_ID`, `APPLE_KEY_ID`, `APPLE_PRIVATE_KEY` (.p8 PEM; escaped newline desteklenir), `APPLE_TOKEN_ENCRYPTION_KEY` (Fernet anahtarı) gerekir. Örnek değişkenler `.env.example` içindedir; gerçek değerleri kaynak kontrolüne koymayın. Fernet anahtarı `cryptography.fernet.Fernet.generate_key()` ile oluşturulur. iOS/Web/BFF'ye bu özel anahtarları vermeyin. Yapılandırma yoksa Apple giriş 503 ile kapalı kalır, email/password akışı etkilenmez. Native client ID dışında Web Services ID desteği bu akışta etkin değildir.

API ve maintenance başlatıldığında yeni Alembic migration çalışır. Şifreleme anahtarını mevcut kullanıcılar ve bekleyen işler varken değiştirmek belirteçleri okunamaz yapar: yedeklemede anahtarı ayrıca koruyun; anahtar rotasyonu migration planı gerektirir.

## Silme ve tekrar deneme

Kullanıcı/veri silme ve şifreli token'ın `apple_revocations` tablosuna aktarılması aynı SQL transaction'dadır. Kuyrukta email/user ID/ham token yoktur; yalnız şifreli belirteç, iş ID, deneme sayısı ve sonraki deneme zamanı vardır. Maintenance en fazla 5 işi row lock ile işler; geçici hata/config hatasında 1 saate kadar artan aralıkla yeniden dener. 200 yanıtı sonrasında iş tamamen silinir; başarılı işler için token geçmişi saklanmaz. Apple iptal çağrısı idempotent olduğundan provider yanıtından sonra DB commit kesilirse tekrar denenebilir. Bakım servisini çalıştırın, `Apple revocation retry required` uyarılarını ve bekleyen en eski iş yaşını operasyonel olarak takip edin. Sürekli hata otomatik olarak çözülmüş sayılmaz.

Önceden yalnız identity token ile açılmış hesaplarda iptal edilebilir token yoktur. Sonraki başarılı Apple girişte saklanır; kullanıcı giriş yapmadan silme isterse hesap yine silinir. Uygulamadaki silme açıklaması Apple bağlantısının iPhone Ayarlar > adın > Apple ile Giriş bölümünden elle kaldırılabileceğini belirtir. Apple bu eski-token istisnasında hesap silmeyi engellememeyi ister: [TN3194](https://developer.apple.com/documentation/technotes/tn3194-handling-account-deletions-and-revoking-tokens-for-sign-in-with-apple).

## Doğrulama

Yerel mock testleri kod/subject uyuşmazlığı, şifreleme, eksik konfigürasyonda kodu tüketmeme, silme/outbox atomik aktarımı ve hata/başarı retry yollarını kapsar. Gerçek Apple çağrısı yapılmadı. Apple Developer portalında entitlement/provisioning ve anahtar hazırlanıp gerçek cihazda ilk giriş, tekrar giriş, hesabı silme ve Apple yetkisinin kaldırılması doğrulanmadan App Store için tamamlandı sayılmaz.

Protokol: [token exchange](https://developer.apple.com/documentation/signinwithapplerestapi/generate-and-validate-tokens), [token revocation](https://developer.apple.com/documentation/signinwithapplerestapi/revoke-tokens).
