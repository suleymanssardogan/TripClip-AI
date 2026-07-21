"use client";

import Navbar from "@/components/Navbar";
import { Share2, Link as LinkIcon } from "lucide-react";

export default function SharePage() {
  return (
    <div className="min-h-screen bg-bg pt-32 px-6">
      <Navbar />
      <div className="max-w-2xl mx-auto text-center">
        <h1 className="font-display font-black text-4xl text-text mb-6">Maceranı Paylaş</h1>
        <p className="text-text-secondary mb-12">Oluşturduğun seyahat planlarını arkadaşlarınla paylaş veya toplulukla paylaşarak başkalarına ilham ol.</p>

        <div className="grid md:grid-cols-2 gap-6">
          <div className="bg-surface border border-border p-8 rounded-lg">
            <div className="w-12 h-12 bg-accent/10 border border-accent/20 rounded-md flex items-center justify-center mb-6">
              <LinkIcon className="text-accent-text w-6 h-6" />
            </div>
            <h3 className="font-display font-bold text-xl text-text mb-2">Özel Link</h3>
            <p className="text-sm text-text-tertiary mb-4">Sadece linki paylaştığın kişilerin görebileceği seyahat albümleri oluştur.</p>
          </div>

          <div className="bg-surface border border-border p-8 rounded-lg">
            <div className="w-12 h-12 bg-route/10 border border-route/20 rounded-md flex items-center justify-center mb-6">
              <Share2 className="text-route w-6 h-6" />
            </div>
            <h3 className="font-display font-bold text-xl text-text mb-2">Toplulukta Yayınla</h3>
            <p className="text-sm text-text-tertiary mb-4">Planını &apos;Keşfet&apos; sayfasında yayınla ve diğer gezginlere yardımcı ol.</p>
          </div>
        </div>
      </div>
    </div>
  );
}
