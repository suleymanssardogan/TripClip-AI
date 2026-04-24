# TripClip AI — Design System & UI Guide

> **Vizyon:** "Luxury travel tech" — seyahat editoryal estetikle modern yapay zeka arayüzünü birleştiren, karanlık zemin üzerinde neon vurgulu, bento grid temelli bir tasarım dili.
>
> **İlham:** [Eloura Journeys](https://elourajourneys.com) (editoryal lüks) + Bruno Bento Grid (modern kart düzeni) + Kendi dark/neon sistemi

---

## 1. Renk Paleti

### Temel Renkler

| Token | Hex | Kullanım |
|---|---|---|
| `--color-bg` | `#080B14` | Sayfa arka planı |
| `--color-surface` | `#0F1521` | Kart / panel arka planı |
| `--color-surface-2` | `#1A2235` | İkincil yüzey (hover, nested) |
| `--color-border` | `rgba(255,255,255,0.06)` | Varsayılan çerçeve |
| `--color-border-accent` | `rgba(77,255,195,0.15)` | Neon çerçeve |

### Metin Renkleri

| Token | Hex | Kullanım |
|---|---|---|
| `--color-on-surface` | `#E2F0FF` | Birincil metin |
| `--color-on-surface-variant` | `#6B8CAE` | İkincil / yardımcı metin |
| `--color-on-surface-muted` | `#3A5068` | Placeholder / devre dışı |

### Vurgu Renkleri

| Token | Hex | Kullanım |
|---|---|---|
| `--color-primary` | `#4DFFC3` | Ana aksiyon, link, neon |
| `--color-primary-dim` | `rgba(77,255,195,0.10)` | Arka plan tonu |
| `--color-purple` | `#8B5CF6` | Gradient ikinci ton |
| `--color-coral` | `#FF6B4A` | Uyarı / sıcak vurgu |
| `--color-gold` | `#F5C842` | Lüks / premium badge |
| `--color-emerald` | `#34D399` | Başarı / tamamlandı |
| `--color-amber` | `#FBBF24` | İşleniyor / bekliyor |

### Bento Kart Renkleri (Dashboard Grid)
Her kart kendi ton kimliğine sahip — tek renk baskın, diğerleri arka planda:

| Kart | Arka Plan | İkincil |
|---|---|---|
| Hero / ana kart | `#0F1521` + neon border | `#4DFFC3` |
| İstatistik (büyük) | `#1A2A1A` (koyu yeşil) | `#4DFFC3` |
| APR / sayı kartı | `#3D1E0A` (koyu turuncu) | `#FF6B4A` |
| Kullanıcı / profil | `#F5C842` (sarı/gold) | `#080B14` |
| Görsel kart | Gerçek seyahat fotoğrafı | overlay |
| Aksiyon kartı | `#1E1A3A` (koyu mor) | `#8B5CF6` |

---

## 2. Tipografi

**Font Ailesi:** Inter (birincil) + Playfair Display (display / luxury başlıklar)

```css
--font-primary: 'Inter', sans-serif;
--font-display: 'Playfair Display', serif;  /* Eloura ilhamı — editorial hissi */
```

### Hiyerarşi

| Seviye | Font | Boyut | Ağırlık | Kullanım |
|---|---|---|---|---|
| `display` | Playfair Display | 56–72px | 700 | Hero slogan, büyük bento kart başlığı |
| `h1` | Inter | 36–48px | 800 | Sayfa başlığı |
| `h2` | Inter | 24–32px | 700 | Bölüm başlığı |
| `h3` | Inter | 18–20px | 600 | Kart başlığı |
| `body` | Inter | 15–16px | 400 | Normal metin |
| `caption` | Inter | 11–12px | 500 | Etiket, badge, timestamp |
| `stat` | Inter | 32–48px | 900 | Büyük rakam (istatistik) |

---

## 3. Efektler & Stiller

### Glass Morphism
```css
.glass {
  background: rgba(15, 21, 33, 0.70);
  backdrop-filter: blur(24px);
  border: 1px solid rgba(255, 255, 255, 0.06);
}
```

### Neon Kart
```css
.neon-card {
  background: rgba(15, 21, 33, 0.80);
  border: 1px solid rgba(77, 255, 195, 0.15);
  box-shadow: 0 4px 24px rgba(0,0,0,0.4),
              inset 0 1px 0 rgba(77, 255, 195, 0.05);
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}
.neon-card:hover {
  border-color: rgba(77, 255, 195, 0.35);
  box-shadow: 0 8px 32px rgba(0,0,0,0.5),
              0 0 24px rgba(77, 255, 195, 0.10);
  transform: translateY(-2px);
}
```

### Gradient Metin
```css
.gradient-text {
  background: linear-gradient(135deg, #4DFFC3 0%, #8B5CF6 50%, #FF6B4A 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}
```

### Arka Plan Grid Deseni
```css
body {
  background-image:
    linear-gradient(rgba(77,255,195,0.025) 1px, transparent 1px),
    linear-gradient(90deg, rgba(77,255,195,0.025) 1px, transparent 1px);
  background-size: 40px 40px;
}
```

---

## 4. Spacing & Border Radius

```
spacing-xs:   4px
spacing-sm:   8px
spacing-md:   16px
spacing-lg:   24px
spacing-xl:   32px
spacing-2xl:  48px
spacing-3xl:  64px

radius-sm:    12px   → badge, chip
radius-md:    16px   → buton
radius-lg:    24px   → küçük kart
radius-xl:    32px   → büyük kart, bento cell
radius-2xl:   40px   → hero kart
```

---

## 5. Bileşen Kataloğu

### 5.1 Button

```
Primary:    bg=#4DFFC3, text=#080B14, font-bold, radius-md
Secondary:  bg=transparent, border=rgba(255,255,255,0.10), text=#E2F0FF
Danger:     bg=rgba(255,107,74,0.10), border=rgba(255,107,74,0.30), text=#FF6B4A
Ghost:      bg=transparent, text=#6B8CAE, hover:text=#E2F0FF
```

### 5.2 Badge / Chip

```
Completed:  bg=rgba(52,211,153,0.10),  text=#34D399,  "● Tamamlandı"
Processing: bg=rgba(251,191,36,0.10),  text=#FBBF24,  "◌ İşleniyor"
Failed:     bg=rgba(255,107,74,0.10),  text=#FF6B4A,  "✕ Hata"
Premium:    bg=rgba(245,200,66,0.10),  text=#F5C842,  "★ Premium"
```

### 5.3 Stat Card
```
┌─────────────────────────────┐
│  [İkon]                     │
│  ETIKET (12px, uppercase)   │
│  123    (40px, font-black)  │
│  Alt metin (12px, muted)    │
└─────────────────────────────┘
```

### 5.4 Plan / Trip Card (Liste)
```
┌──[Resim/İkon]──[Başlık]──[Meta]──[Badge]──[→]─┐
│  64x64 px     bold 16px   12px muted            │
└────────────────────────────────────────────────┘
```

---

## 6. Dashboard — Bento Grid Düzeni

> Referans: Görseldeki Bruno/Claudia Carvalho bento grid

### 6.1 Genel Grid
```
Desktop (≥1280px): 3 sütun, otomatik satır yüksekliği
Tablet  (≥768px):  2 sütun
Mobil   (<768px):  1 sütun (kartlar sıralanır)

gap: 16px (--spacing-md)
padding: 24px container içi
```

### 6.2 Hücre Haritası

```
┌────────────────────┬──────────────┬────────────────────┐
│                    │  📈 AI Stats │                    │
│  Seyahat Fotoğrafı │  "Tamamlanan │  Seyahat Fotoğrafı │
│  (col-span 1)      │   Analiz: 24"│  (col-span 1)      │
│  row-span 1        │  turuncu bg  │  row-span 1        │
├────────────────────┼──────────────┴────────────────────┤
│                    │                                    │
│  "Gezi             │  📱 Uygulama Önizleme             │
│   Planlarım"       │  (orta kart — telefon görseli)    │
│  büyük slogan      │                                   │
│  koyu mavi bg      ├──────────────┬────────────────────┤
│  col-span 1        │  👤 Kullanıcı│  Seyahat Fotoğrafı │
│  row-span 2        │  "10₺'den    │  (küçük kart)      │
│                    │   analiz et" │  row-span 1        │
│                    │  gold bg     │                    │
└────────────────────┴──────────────┴────────────────────┘
```

### 6.3 Kart Tanımları

| Hücre | İçerik | Renk Teması | Boyut |
|---|---|---|---|
| **A** Seyahat Görseli | Kullanıcının en son planından fotoğraf | Gerçek görsel + overlay | 1×1 |
| **B** AI İstatistiği | "Tamamlanan Analiz: 24" + mini grafik | `#3D1E0A` turuncu | 1×1 |
| **C** Seyahat Görseli | Platform öne çıkan konum fotoğrafı | Gerçek görsel + overlay | 1×1 |
| **D** Hero Slogan | "Gezi Planlarım" büyük serif + açıklama | `#0F0F3A` koyu mavi | 1×2 |
| **E** Uygulama Önizleme | Mobil ekran görseli veya harita | `#1A1A2E` + mor gradient | 2×1 |
| **F** Kullanıcı CTA | Avatar + "10₺'den analiz et" + buton | `#F5C842` gold | 1×1 |
| **G** Lokasyon Görseli | Son gezilen şehir fotoğrafı | Gerçek görsel + overlay | 1×1 |

### 6.4 Tailwind CSS Sınıfları

```tsx
// Ana grid wrapper
<div className="grid grid-cols-3 grid-rows-[auto] gap-4">

// Normal kart (1×1)
<div className="col-span-1 row-span-1 rounded-[32px] overflow-hidden">

// Hero kart (1 genişlik, 2 yükseklik)
<div className="col-span-1 row-span-2 rounded-[32px] p-8 flex flex-col justify-end"
     style={{ background: '#0F0F3A' }}>

// Geniş kart (2 genişlik, 1 yükseklik)
<div className="col-span-2 row-span-1 rounded-[32px] overflow-hidden">
```

---

## 7. Sayfa Haritası

| Route | Sayfa | Layout |
|---|---|---|
| `/` | Landing / Welcome | Tam ekran hero + feature cards |
| `/login` | Giriş | Ortalanmış glass form |
| `/signup` | Kayıt | Ortalanmış glass form |
| `/dashboard` | **Bento Grid Dashboard** | 3 sütun bento grid |
| `/analyze/[id]` | Video Analiz Sonucu | Harita + lokasyon listesi |
| `/editor/[id]` | Gezi Planı Düzenleyici | Timeline + gün bazlı düzen |
| `/explore` | Keşfet (public feed) | Masonry grid |
| `/share/[id]` | Paylaşım Sayfası | Hero stat + harita |

---

## 8. Animasyon

```
Sayfa giriş:    fadeIn + slideUp, duration 400ms, easing ease-out
Kart hover:     translateY(-2px), duration 300ms
Sayı sayacı:    countUp animasyonu (stat kartlar)
Yükleme:        pulse skeleton (kart placeholder)
Bento grid:     staggered entrance — kartlar sırayla 80ms arayla girer
```

### Framer Motion Preset
```tsx
const cardVariants = {
  hidden: { opacity: 0, y: 24 },
  visible: (i: number) => ({
    opacity: 1, y: 0,
    transition: { delay: i * 0.08, duration: 0.4, ease: "easeOut" }
  })
};
```

---

## 9. Görsel İçerik Stratejisi

> Eloura Journeys ilhamı: her kart bir "seyahat anısı" gibi hissettirmeli.

- **Fotoğraf tonu:** Açık hava, gün ışığı, doğal renkler — koyu arayüzle kontrast yaratır
- **Overlay:** `linear-gradient(to top, rgba(8,11,20,0.85) 0%, transparent 60%)` — metin okunabilirliği için
- **Aspect ratio:** Görsel kartlar `aspect-[4/3]` veya `aspect-square`
- **Placeholder:** Lokasyon başına emoji + gradient arka plan (fotoğraf yokken)

```tsx
// Görsel kart örneği
<div className="relative aspect-[4/3] rounded-[32px] overflow-hidden">
  <img src={plan.thumbnail} className="w-full h-full object-cover" />
  <div className="absolute inset-0 bg-gradient-to-t from-[#080B14]/85 to-transparent" />
  <div className="absolute bottom-0 left-0 p-6">
    <p className="text-white font-bold text-xl">{plan.top_location}</p>
    <p className="text-white/60 text-sm">{plan.locations_count} lokasyon</p>
  </div>
</div>
```

---

## 10. Referanslar

| Kaynak | Ne aldık |
|---|---|
| [Eloura Journeys](https://elourajourneys.com/bespoke-luxury-urban-discoveries/) | Editoryal lüks ton, seyahat fotoğrafı kullanımı, generous whitespace |
| Bruno Bento Grid (Claudia Carvalho) | Bento grid düzeni, renkli kart kimliği, büyük tipografi |
| Mevcut globals.css | Dark bg (#080B14), neon primary (#4DFFC3), glass morphism |
| Framer Motion docs | Staggered animasyon sistemi |

---

## 11. Uygulama Öncelik Sırası

1. **[YÜK-1]** `dashboard/page.tsx` → Bento Grid'e dönüştür
2. **[YÜK-2]** `globals.css` → Gold token + Playfair Display ekle
3. **[YÜK-3]** Görsel kartlarda overlay sistemi
4. **[YÜK-4]** `explore/page.tsx` → Masonry grid layout
5. **[YÜK-5]** `analyze/[id]` → Harita entegrasyonu iyileştirmesi
