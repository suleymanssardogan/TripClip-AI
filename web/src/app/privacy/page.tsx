import Link from "next/link";

const operator = process.env.NEXT_PUBLIC_LEGAL_OPERATOR_NAME?.trim();
const contact = process.env.NEXT_PUBLIC_LEGAL_CONTACT_EMAIL?.trim();

export default function PrivacyPage() {
  return (
    <main className="min-h-screen bg-bg px-6 py-16 text-text">
      <article className="mx-auto max-w-3xl space-y-8 leading-7">
        <Link href="/" className="inline-block text-sm text-accent-text hover:underline">← TripClip ana sayfa</Link>
        <header className="space-y-3">
          <h1 className="font-display text-3xl font-black sm:text-4xl">Gizlilik ve Kişisel Veriler</h1>
          <p className="text-text-secondary">Son güncelleme: 1 Ekim 2026</p>
          {(!operator || !contact) && (
            <p className="rounded-md border border-warning/40 bg-warning/10 p-4 text-sm text-text" role="status">
              Bu metnin veri sorumlusu ve iletişim bilgileri henüz tamamlanmadı. Yayın öncesinde doldurulacak.
            </p>
          )}
        </header>

        <section className="space-y-2">
          <h2 className="font-display text-xl font-bold">Veri sorumlusu ve iletişim</h2>
          <p className="text-text-secondary">TripClip AI hizmetinin veri sorumlusu: {operator || "[Yasal kişi veya şirket adı eklenecek]"}.</p>
          <p className="text-text-secondary">Kişisel verilerle ilgili başvurular için: {contact ? <a href={`mailto:${contact}`} className="text-accent-text hover:underline">{contact}</a> : "[İletişim e-postası eklenecek]"}.</p>
        </section>

        <section className="space-y-2">
          <h2 className="font-display text-xl font-bold">İşlenen bilgiler</h2>
          <p className="text-text-secondary">Hesap açtığınızda e-posta adresi, kullanıcı adı, şifre özeti ve giriş sağlayıcısının hesap kimliği; hizmeti kullandığınızda yüklediğiniz videolar, paylaştığınız bağlantılar, oluşturduğunuz gezi ve rota içerikleri, davetler ve asistana yazdığınız mesajlar işlenir. İşlem güvenliği için IP adresi, oturum ve hata kayıtları; isteğe bağlı kullanım analitiği varsayılan olarak kapalıdır. Hata izleme etkinleştirildiğinde istek içeriği, kullanıcı kimliği ve yerel değişkenler dışarı gönderilmez.</p>
        </section>

        <section className="space-y-2">
          <h2 className="font-display text-xl font-bold">Amaçlar ve toplama yöntemi</h2>
          <p className="text-text-secondary">Bilgiler, web sitesi ve iOS uygulamasındaki formlar, yüklemeler ve kullanım sırasında otomatik olarak toplanır. Hesap ve oturum yönetimi, video analizi, gezi önerileri, paylaşım, şifre sıfırlama, güvenlik ve hata giderme için kullanılır. Sözleşmenin kurulması veya ifası, hukuki yükümlülükler ve uygun olduğu durumlarda meşru menfaat ya da açık rıza dayanakları yayından önce veri işleme envanteriyle eşleştirilip doğrulanacaktır.</p>
        </section>

        <section className="space-y-2">
          <h2 className="font-display text-xl font-bold">Hizmet sağlayıcıları ve aktarım</h2>
          <p className="text-text-secondary">Video ve gezi içerikleri, özellikleri sağlamak için yapılandırılmış yapay zekâ sağlayıcılarına (varsayılan olarak Google Gemini), konum arama için OpenStreetMap Nominatim hizmetine ve barındırma altyapısına aktarılabilir. Google ile giriş, e-posta gönderimi ve hata izleme etkinleştirilirse ilgili sağlayıcılar da yalnızca bu işlevler için veri işler. Üretim ortamında Gemini, Ollama, Google Vision ve konum servislerine veri göndermek, ilgili sağlayıcı veri işleme ve aktarım incelemesinden geçirilene kadar engellenir. Sağlayıcının onaylanması tek başına hukuki dayanak oluşturmaz; alıcı, ülke, işleme şartı ve uygulanacak aktarım güvencesi veri sorumlusu tarafından yayından önce belirlenir.</p>
        </section>

        <section className="space-y-2">
          <h2 className="font-display text-xl font-bold">Paylaşım, saklama ve silme</h2>
          <p className="text-text-secondary">Video analizleri varsayılan olarak özeldir ve keşfet akışına otomatik eklenmez. Açık paylaşım bağlantısı oluşturduğunuz gezi içeriklerini bağlantıya sahip kişiler görebilir. Hesabınızı uygulama içinden silebilirsiniz; bu işlem aktif sistemlerdeki hesaba bağlı kayıtların silinmesini başlatır. Varsayılan ayarlarda tamamlanmış analizlerin ham video dosyaları yüklenmelerinden 24 saat, başarısız yüklemeler 7 gün sonra temizlenir; devam eden işlemler hariçtir. Oluşturulan analiz ve gezi kayıtları siz silene veya hesabınızı kapatana kadar kalır. Dosya silme başarısız olursa tekrar denenecek bir imha kaydı tutulur. İmha işlem kayıtları kişisel içerik olmadan en az üç yıl saklanır. Yedekler ve güvenlik günlüklerinin süreleri ile geri yükleme sonrası silinen verilerin yeniden temizlenmesi yayından önce işletme prosedüründe kesinleştirilecektir.</p>
        </section>

        <section className="space-y-2">
          <h2 className="font-display text-xl font-bold">Haklarınız</h2>
          <p className="text-text-secondary">Kişisel verilerinizin işlenip işlenmediğini öğrenme, bilgi ve düzeltme isteme, koşulları oluştuğunda silinmesini talep etme ve diğer yasal haklarınız için yukarıdaki iletişim adresine başvurabilirsiniz. Başvurular ilgili mevzuata göre değerlendirilir.</p>
        </section>
      </article>
    </main>
  );
}
