"""
TripClip AI — App Icon Generator
Çalıştır: python3 generate_icon.py
"""

from PIL import Image, ImageDraw, ImageFont
import math, os

OUT = "TripClipAI/Assets.xcassets/AppIcon.appiconset"
os.makedirs(OUT, exist_ok=True)

def draw_icon(size: int) -> Image.Image:
    img  = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    s    = size

    # ── Arka plan: koyu mavi → mor gradyan ──
    for y in range(s):
        t = y / s
        r = int(10  + t * 15)
        g = int(14  + t * 10)
        b = int(39  + t * 40)
        draw.line([(0, y), (s, y)], fill=(r, g, b, 255))

    # ── Yuvarlatılmış köşeler için maske ──
    radius = int(s * 0.22)
    mask   = Image.new("L", (s, s), 0)
    md     = ImageDraw.Draw(mask)
    md.rounded_rectangle([0, 0, s - 1, s - 1], radius=radius, fill=255)
    img.putalpha(mask)
    draw   = ImageDraw.Draw(img)

    # ── Neon yeşil/cyan hale (sol üst) ──
    cx, cy, cr = int(s * 0.3), int(s * 0.25), int(s * 0.55)
    for r_step in range(cr, 0, -max(1, cr // 40)):
        alpha = int(30 * (1 - r_step / cr))
        draw.ellipse(
            [cx - r_step, cy - r_step, cx + r_step, cy + r_step],
            fill=(77, 255, 195, alpha)
        )

    # ── Harita pin ikonu ──
    # Pin gövdesi (daire)
    pin_cx = s // 2
    pin_cy = int(s * 0.38)
    pin_r  = int(s * 0.20)

    # Dış gölge/glow
    for offset in range(int(s * 0.04), 0, -1):
        alpha = int(120 * (1 - offset / (s * 0.04)))
        draw.ellipse(
            [pin_cx - pin_r - offset, pin_cy - pin_r - offset,
             pin_cx + pin_r + offset, pin_cy + pin_r + offset],
            fill=(77, 255, 195, alpha)
        )

    # Pin dairesi
    draw.ellipse(
        [pin_cx - pin_r, pin_cy - pin_r, pin_cx + pin_r, pin_cy + pin_r],
        fill=(255, 255, 255, 255)
    )

    # Pin içi (neon nokta)
    inner = int(pin_r * 0.45)
    draw.ellipse(
        [pin_cx - inner, pin_cy - inner, pin_cx + inner, pin_cy + inner],
        fill=(10, 14, 39, 255)
    )

    # Pin kuyruğu (aşağı üçgen)
    tail_h = int(s * 0.22)
    tail_w = int(pin_r * 0.55)
    tail_top_y = pin_cy + pin_r - int(pin_r * 0.1)
    tip_y      = pin_cy + pin_r + tail_h
    draw.polygon(
        [
            (pin_cx - tail_w, tail_top_y),
            (pin_cx + tail_w, tail_top_y),
            (pin_cx,          tip_y),
        ],
        fill=(255, 255, 255, 255)
    )

    # ── "AI" yazısı: pin altında ──
    text_y    = int(s * 0.72)
    font_size = max(8, int(s * 0.15))
    try:
        font  = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", font_size)
        font2 = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", max(6, int(font_size * 0.55)))
    except Exception:
        font  = ImageFont.load_default()
        font2 = font

    # "AI" — neon renk
    draw.text((s // 2, text_y), "AI", font=font,
              fill=(77, 255, 195, 255), anchor="mm")

    # Altında ince "TripClip" yazısı
    sub_y = text_y + font_size + max(2, int(s * 0.02))
    draw.text((s // 2, sub_y), "TripClip", font=font2,
              fill=(255, 255, 255, 160), anchor="mm")

    return img


# ── 1024x1024 standart ikon ──
icon = draw_icon(1024)
icon.save(f"{OUT}/AppIcon-1024.png")
print("✅ AppIcon-1024.png oluşturuldu")

# ── Karanlık mod varyantı (biraz daha koyu arka plan) ──
dark = draw_icon(1024)
# Karanlık: arka planı daha koyu yap (basit overlay)
overlay = Image.new("RGBA", (1024, 1024), (0, 0, 20, 60))
dark    = Image.alpha_composite(dark, overlay)
dark.save(f"{OUT}/AppIcon-1024-dark.png")
print("✅ AppIcon-1024-dark.png oluşturuldu")

# ── Tinted varyant (monokrom benzeri) ──
tinted = draw_icon(1024).convert("L").convert("RGBA")
tinted.save(f"{OUT}/AppIcon-1024-tinted.png")
print("✅ AppIcon-1024-tinted.png oluşturuldu")

# ── Contents.json güncelle ──
import json
contents = {
  "images": [
    {"idiom": "universal", "platform": "ios", "size": "1024x1024",
     "filename": "AppIcon-1024.png"},
    {"idiom": "universal", "platform": "ios", "size": "1024x1024",
     "filename": "AppIcon-1024-dark.png",
     "appearances": [{"appearance": "luminosity", "value": "dark"}]},
    {"idiom": "universal", "platform": "ios", "size": "1024x1024",
     "filename": "AppIcon-1024-tinted.png",
     "appearances": [{"appearance": "luminosity", "value": "tinted"}]},
  ],
  "info": {"author": "xcode", "version": 1}
}
with open(f"{OUT}/Contents.json", "w") as f:
    json.dump(contents, f, indent=2)
print("✅ Contents.json güncellendi")
print(f"\n📁 Dosyalar: {OUT}/")
