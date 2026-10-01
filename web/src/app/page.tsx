import Image from "next/image";
import Link from "next/link";
import { ArrowRight, ArrowUpRight } from "lucide-react";
import Navbar from "@/components/Navbar";
import { buttonVariants } from "@/components/ui/Button";

const steps = [
  { number: "01", title: "Videoyu ekle", description: "Beğendiğin gezi videosunu paylaş. Gerisini TripClip'e bırak." },
  { number: "02", title: "Yerleri keşfet", description: "Videoda geçen durakları tek bir yerde gör, istediklerini kaydet." },
  { number: "03", title: "Rotanı kur", description: "Durakları sırala, günlere ayır ve sana uyan bir plan oluştur." },
];

const sampleStops = [
  { time: "10.00", name: "Galata Kulesi", area: "Beyoğlu", number: "01" },
  { time: "12.30", name: "Karaköy", area: "Beyoğlu", number: "02" },
  { time: "15.00", name: "Balat", area: "Fatih", number: "03" },
];

function ProductPreview() {
  return (
    <div className="overflow-hidden rounded-2xl border border-border bg-surface shadow-[0_32px_90px_-52px_rgba(24,37,49,0.32)]" aria-label="TripClip örnek gezi planı arayüzü">
      <div className="flex items-center justify-between border-b border-border px-5 py-4 sm:px-7">
        <span className="font-display text-base font-bold tracking-[-0.055em] text-text">tripclip<span className="text-accent-text">.</span></span>
        <span className="rounded-md border border-border bg-surface2 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-text-secondary">Örnek arayüz</span>
      </div>
      <div className="grid lg:grid-cols-[1.2fr_0.8fr]">
        <div className="px-6 py-7 sm:px-10 sm:py-9">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.17em] text-accent-text">Gezi planı / İstanbul</p>
              <h3 className="mt-3 font-display text-[clamp(1.7rem,3vw,2.4rem)] font-bold tracking-[-0.05em] text-text">Şehirde bir gün</h3>
              <p className="mt-2 text-sm text-text-secondary">Seçtiğin yerlerden oluşan örnek bir rota.</p>
            </div>
            <span className="hidden rounded-md bg-accent/10 px-3 py-1.5 text-xs font-semibold text-accent-text sm:block">1. gün</span>
          </div>
          <div className="mt-8 border-t border-border">
            {sampleStops.map((stop) => (
              <div key={stop.number} className="grid grid-cols-[3.3rem_1fr_auto] items-center gap-3 border-b border-border py-4 sm:grid-cols-[4rem_1fr_auto] sm:gap-5">
                <span className="font-mono text-xs text-text-tertiary">{stop.time}</span>
                <div className="min-w-0"><p className="font-semibold text-text">{stop.name}</p><p className="mt-0.5 text-xs text-text-secondary">{stop.area}</p></div>
                <span className="font-mono text-xs text-accent-text">{stop.number}</span>
              </div>
            ))}
          </div>
        </div>
        <div className="flex flex-col justify-between border-t border-border bg-[#f3f7f9] px-6 py-7 dark:bg-surface2 lg:border-l lg:border-t-0 sm:px-9 sm:py-9">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.17em] text-text-secondary">Plan özeti</p>
            <p className="mt-5 font-display text-5xl font-bold tracking-[-0.06em] text-text">3 <span className="text-xl font-medium tracking-normal text-text-secondary">durak</span></p>
            <p className="mt-2 text-sm leading-6 text-text-secondary">Videodaki fikirler artık düzenleyebileceğin bir gezi planı.</p>
          </div>
          <div className="mt-8 border-t border-border pt-5">
            <p className="text-xs font-semibold uppercase tracking-[0.14em] text-text-tertiary">Sıradaki adım</p>
            <p className="mt-2 text-sm font-semibold text-text">Durakları kendine göre sırala.</p>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-bg">
      <Navbar />
      <main>
        <section className="bg-surface px-5 pb-20 pt-28 sm:px-8 md:pb-24 md:pt-36">
          <div className="mx-auto grid max-w-7xl items-center gap-12 md:grid-cols-[0.92fr_1.08fr] md:gap-10 lg:gap-16">
            <div className="max-w-xl">
              <p className="text-xs font-bold uppercase tracking-[0.2em] text-accent-text">Videodan yolculuğa</p>
              <h1 className="mt-6 font-display text-[clamp(3rem,5.7vw,5.7rem)] font-bold leading-[1.04] tracking-[-0.07em] text-text">
                Gördüğün yerler, <span className="text-accent-text">gideceğin yerler.</span>
              </h1>
              <p className="mt-7 max-w-lg text-base leading-8 text-text-secondary sm:text-lg">
                TripClip, gezi videolarındaki durakları bulur. Sen de onları kaydeder, düzenler ve kendine ait bir rotaya dönüştürürsün.
              </p>
              <div className="mt-9 flex flex-wrap gap-3">
                <Link href="/signup" className={buttonVariants({ size: "lg" })}>Ücretsiz başla <ArrowUpRight className="h-4 w-4" /></Link>
                <Link href="/explore" className={buttonVariants({ size: "lg", variant: "outline" })}>Gezileri keşfet</Link>
              </div>
              <div className="mt-12 border-t border-border pt-5 text-sm text-text-secondary">
                <span className="font-semibold text-text">Bir video.</span> Yeni duraklar. Sana ait bir plan.
              </div>
            </div>
            <figure className="relative overflow-hidden rounded-[1.4rem] bg-surface2">
              <div className="relative aspect-[4/4.15] sm:aspect-[4/3] md:aspect-[4/4.5] lg:aspect-[4/3.7]">
                <Image src="/images/istanbul-editorial.webp" alt="İstanbul kıyısı, Boğaz ve vapurların temsili seyahat görseli" fill priority sizes="(max-width: 767px) 100vw, 55vw" className="object-cover object-[63%_center]" />
              </div>
              <figcaption className="absolute inset-x-0 bottom-0 flex items-center justify-between gap-4 bg-surface/95 px-5 py-4 text-xs text-text-secondary backdrop-blur-sm sm:px-6">
                <span><strong className="font-semibold text-text">İstanbul, Türkiye</strong> · Temsili görsel</span>
                <span className="font-mono text-text-tertiary">01 / 03</span>
              </figcaption>
            </figure>
          </div>
        </section>

        <section id="nasil-calisir" className="scroll-mt-20 px-5 py-20 sm:px-8 lg:py-28">
          <div className="mx-auto max-w-7xl">
            <div className="max-w-2xl">
              <p className="text-xs font-bold uppercase tracking-[0.2em] text-accent-text">Nasıl çalışır?</p>
              <h2 className="mt-4 font-display text-[clamp(2rem,4vw,3.5rem)] font-bold leading-tight tracking-[-0.055em] text-text">İlhamdan plana, üç adımda.</h2>
              <p className="mt-4 text-base leading-7 text-text-secondary">Bir gezi videosundan yola çık. Gitmek istediğin yerleri kendi hızında planla.</p>
            </div>
            <div className="mt-12 grid gap-4 md:grid-cols-3">
              {steps.map((step) => (
                <div key={step.number} className="rounded-xl border border-border bg-surface px-6 py-7 sm:px-7 sm:py-8">
                  <span className="font-mono text-sm font-semibold text-accent-text">{step.number}</span>
                  <h3 className="mt-12 font-display text-xl font-bold tracking-[-0.035em] text-text">{step.title}</h3>
                  <p className="mt-3 text-sm leading-7 text-text-secondary">{step.description}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="border-y border-border bg-surface px-5 py-20 sm:px-8 lg:py-28">
          <div className="mx-auto max-w-7xl">
            <div className="mb-10 flex flex-col justify-between gap-6 md:flex-row md:items-end">
              <div className="max-w-2xl">
                <p className="text-xs font-bold uppercase tracking-[0.2em] text-accent-text">Hepsi bir arada</p>
                <h2 className="mt-4 font-display text-[clamp(2rem,4vw,3.5rem)] font-bold leading-tight tracking-[-0.055em] text-text">Kaydettiğin yerler, hazır bir yolculuk.</h2>
              </div>
              <p className="max-w-sm text-sm leading-7 text-text-secondary">Duraklarını tek ekranda gör, dilediğin gibi düzenle ve planını paylaş.</p>
            </div>
            <ProductPreview />
          </div>
        </section>

        <section className="px-5 py-20 sm:px-8 lg:py-28">
          <div className="mx-auto flex max-w-7xl flex-col justify-between gap-8 overflow-hidden rounded-2xl bg-[#16548f] px-7 py-10 text-white sm:px-12 sm:py-14 md:flex-row md:items-end dark:bg-[#225d94] lg:px-16 lg:py-16">
            <div className="max-w-2xl">
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-white/70">Sıradaki yolculuğun</p>
              <h2 className="mt-4 font-display text-[clamp(2rem,4vw,3.5rem)] font-bold leading-tight tracking-[-0.055em]">Bir videoyla başlayabilir.</h2>
              <p className="mt-4 max-w-lg text-sm leading-7 text-white/80">Gezi fikirlerini kaydetmeye başla. Gerisini yolda birlikte şekillendiririz.</p>
            </div>
            <Link href="/signup" className="inline-flex shrink-0 items-center justify-center gap-2 rounded-lg bg-white px-7 py-4 text-sm font-semibold text-[#16548f] transition-colors hover:bg-[#edf5fa]">Hesap oluştur <ArrowRight className="h-4 w-4" /></Link>
          </div>
        </section>
      </main>
      <footer className="border-t border-border bg-surface px-5 py-9 sm:px-8">
        <div className="mx-auto flex max-w-7xl flex-col justify-between gap-6 text-sm text-text-secondary sm:flex-row sm:items-center">
          <Link href="/" className="font-display text-lg font-bold tracking-[-0.05em] text-text">tripclip<span className="text-accent-text">.</span></Link>
          <div className="flex flex-wrap gap-x-7 gap-y-3"><Link href="/explore" className="hover:text-text">Keşfet</Link><Link href="/#nasil-calisir" className="hover:text-text">Nasıl çalışır?</Link><Link href="/privacy" className="hover:text-text">Gizlilik</Link><Link href="/terms" className="hover:text-text">Koşullar</Link></div>
        </div>
      </footer>
    </div>
  );
}
