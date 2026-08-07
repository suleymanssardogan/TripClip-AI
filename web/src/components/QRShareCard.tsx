"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { QrCode, Copy, Check, Smartphone, Download } from "lucide-react";

interface Props {
  url: string;
  title?: string;
  /** Link kopyalandığında çağrılır — analytics event'i bilerek bu bileşenin
   *  dışında (çağıran tarafta) ateşlenir, QRShareCard analytics'ten habersiz
   *  kalır ve her yerde yeniden kullanılabilir. */
  onCopy?: () => void;
}

/**
 * QR kod paylaşım kartı.
 * QR görseli api.qrserver.com tarafından sunulur (zero install).
 */
export default function QRShareCard({ url, title = "Telefonla Paylaş", onCopy }: Props) {
  const [copied, setCopied] = useState(false);

  // Hydration sırasında URL'i client'tan al — SSR'de window yok
  // Telefondan QR okutulunca "localhost" çalışmaz; LAN IP'sine çevir.
  let safeUrl = url;
  try {
    if (url) {
      const u = new URL(url);
      const isLocal = u.hostname === "localhost" || u.hostname === "127.0.0.1";
      if (isLocal) {
        const lanHost =
          process.env.NEXT_PUBLIC_LAN_HOST ||  // .env.local'a ekleyebilirsin
          "10.192.88.86";                       // Mac'in mevcut LAN IP'si
        u.hostname = lanHost;
        safeUrl = u.toString();
      }
    }
  } catch { /* parse hatası — orijinal URL'i kullan */ }

  const qrSrc =
    `https://api.qrserver.com/v1/create-qr-code/` +
    `?size=320x320&margin=8&color=0C0D10&bgcolor=ffffff&qzone=2&data=` +
    encodeURIComponent(safeUrl);

  function handleCopy() {
    navigator.clipboard.writeText(safeUrl).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
      onCopy?.();
    });
  }

  function handleDownload() {
    // QR görselini PNG olarak indir
    const a = document.createElement("a");
    a.href = qrSrc;
    a.download = `tripclip-qr-${Date.now()}.png`;
    a.target = "_blank";
    a.rel = "noopener";
    document.body.appendChild(a);
    a.click();
    a.remove();
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-surface border border-border p-8 rounded-lg flex flex-col items-center text-center gap-5"
    >
      <div className="flex items-center gap-2 text-accent-text">
        <QrCode className="w-5 h-5" />
        <span className="font-mono text-[10px] font-black uppercase tracking-widest">{title}</span>
      </div>

      {/* QR */}
      <div className="bg-white p-4 rounded-md shadow-card">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={qrSrc}
          alt="Plan paylaşım QR kodu"
          width={220}
          height={220}
          className="w-[220px] h-[220px] block"
        />
      </div>

      <p className="text-xs text-text-tertiary max-w-[260px] leading-relaxed">
        <Smartphone className="inline w-3.5 h-3.5 -mt-0.5 mr-1" />
        Kamerayla okut, planı telefonunda aç
      </p>

      {/* Eylemler */}
      <div className="flex gap-2 w-full">
        <button
          onClick={handleCopy}
          className="flex-1 flex items-center justify-center gap-2 py-3 bg-surface2 hover:bg-border border border-border-strong rounded-md text-[10px] font-black uppercase tracking-widest text-text transition-all"
        >
          {copied ? (
            <>
              <Check className="w-3.5 h-3.5 text-success" /> Kopyalandı
            </>
          ) : (
            <>
              <Copy className="w-3.5 h-3.5" /> Linki Kopyala
            </>
          )}
        </button>
        <button
          onClick={handleDownload}
          className="flex-1 flex items-center justify-center gap-2 py-3 bg-accent/10 hover:bg-accent/20 border border-accent/25 rounded-md text-[10px] font-black uppercase tracking-widest text-accent-text transition-all"
        >
          <Download className="w-3.5 h-3.5" /> QR İndir
        </button>
      </div>
    </motion.div>
  );
}
