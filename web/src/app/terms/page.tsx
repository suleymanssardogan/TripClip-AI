import Link from "next/link";

const operator = process.env.NEXT_PUBLIC_LEGAL_OPERATOR_NAME?.trim();
const contact = process.env.NEXT_PUBLIC_LEGAL_CONTACT_EMAIL?.trim();

export default function TermsPage() {
  return (
    <main className="min-h-screen bg-bg px-6 py-16 text-text">
      <article className="mx-auto max-w-3xl space-y-8 leading-7">
        <Link href="/" className="inline-block text-sm text-accent-text hover:underline">← TripClip ana sayfa</Link>
        <header className="space-y-3">
          <h1 className="font-display text-3xl font-black sm:text-4xl">Kullanım Koşulları</h1>
          <p className="text-text-secondary">Son güncelleme: 23 Eylül 2026</p>
          {(!operator || !contact) && (
            <p className="rounded-md border border-warning/40 bg-warning/10 p-4 text-sm text-text" role="status">
              Hizmeti işleten kişi veya şirket ile iletişim bilgileri yayın öncesinde tamamlanacak.
            </p>
          )}
        </header>

        <section className="space-y-2">
          <h2 className="font-display text-xl font-bold">Hizmet</h2>
          <p className="text-text-secondary">TripClip AI ({operator || "[Hizmeti işleten kişi veya şirket adı]"}), kullanıcıların seyahat videolarını analiz edip gezi planları oluşturmasına ve bu planları paylaşmasına yardımcı olur. Hizmetin web sitesi ve iOS uygulaması bu koşullar kapsamında sunulur.</p>
        </section>

        <section className="space-y-2">
          <h2 className="font-display text-xl font-bold">Hesap ve güvenlik</h2>
          <p className="text-text-secondary">Hesap bilgilerinizin doğru ve güncel olmasından, giriş bilgilerinizi korumaktan ve hesabınız üzerinden yaptığınız işlemlerden siz sorumlusunuz. Yetkisiz kullanımdan şüphelenirseniz şifrenizi değiştirip bize bildirin. Hesabınızı uygulama içinden silebilirsiniz.</p>
        </section>

        <section className="space-y-2">
          <h2 className="font-display text-xl font-bold">Yüklediğiniz içerikler</h2>
          <p className="text-text-secondary">Yalnızca kullanma ve paylaşma hakkına sahip olduğunuz video, bağlantı ve diğer içerikleri gönderin. İçeriğinizin sahipliği sizde kalır. Hizmeti sağlamak için içeriği barındırmamıza, işlememize, analiz etmemize ve sizin seçtiğiniz paylaşım bağlantıları üzerinden göstermemize izin verirsiniz. Başkalarının haklarını ihlal eden veya hukuka aykırı içerik göndermeyin.</p>
        </section>

        <section className="space-y-2">
          <h2 className="font-display text-xl font-bold">Yapay zekâ önerileri</h2>
          <p className="text-text-secondary">Konum tespiti, rota ve gezi önerileri otomatik üretilir; hatalı veya güncel olmayan bilgiler içerebilir. Ulaşım, fiyat, çalışma saatleri, erişilebilirlik ve güvenlik bilgilerini karar vermeden önce ilgili kaynaklardan doğrulayın.</p>
        </section>

        <section className="space-y-2">
          <h2 className="font-display text-xl font-bold">Kabul edilmeyen kullanım</h2>
          <p className="text-text-secondary">Hizmeti başkalarının hesaplarına izinsiz erişmek, güvenlik önlemlerini aşmak, aşırı otomatik isteklerle çalışmasını bozmak, zararlı yazılım dağıtmak veya hukuka aykırı içerik işlemek için kullanamazsınız. Bu tür kullanımda ilgili içeriğe veya hesaba erişim durdurulabilir.</p>
        </section>

        <section className="space-y-2">
          <h2 className="font-display text-xl font-bold">Değişiklikler ve iletişim</h2>
          <p className="text-text-secondary">Hizmetin özellikleri geliştirilebilir veya güvenlik ve bakım için geçici olarak kesilebilir. Koşullar değişirse güncel metin ve tarih bu sayfada yayımlanır. Sorularınız için {contact ? <a href={`mailto:${contact}`} className="text-accent-text hover:underline">{contact}</a> : "[İletişim e-postası eklenecek]"} adresinden bize ulaşabilirsiniz.</p>
        </section>

        <p className="border-t border-border pt-6 text-sm text-text-secondary">
          Kişisel verilerin işlenmesine ilişkin bilgiler için <Link href="/privacy" className="text-accent-text hover:underline">Gizlilik ve Kişisel Veriler</Link> sayfasına bakın.
        </p>
      </article>
    </main>
  );
}
