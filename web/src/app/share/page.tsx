"use client";

import Navbar from "@/components/Navbar";
import { Share2, Link as LinkIcon } from "lucide-react";

export default function SharePage() {
  return (
    <div className="min-h-screen bg-background pt-32 px-6">
      <Navbar />
      <div className="max-w-2xl mx-auto text-center">
        <h1 className="text-4xl font-bold mb-6">Maceranı Paylaş</h1>
        <p className="text-muted-foreground mb-12">Oluşturduğun seyahat planlarını arkadaşlarınla paylaş veya toplulukla paylaşarak başkalarına ilham ol.</p>
        
        <div className="grid md:grid-cols-2 gap-6">
          <div className="glass p-8 rounded-3xl">
            <div className="w-12 h-12 bg-primary/10 rounded-xl flex items-center justify-center mb-6">
              <LinkIcon className="text-primary w-6 h-6" />
            </div>
            <h3 className="text-xl font-bold mb-2">Özel Link</h3>
            <p className="text-sm text-muted-foreground mb-4">Sadece linki paylaştığın kişilerin görebileceği seyahat albümleri oluştur.</p>
          </div>
          
          <div className="glass p-8 rounded-3xl">
            <div className="w-12 h-12 bg-emerald-500/10 rounded-xl flex items-center justify-center mb-6">
              <Share2 className="text-emerald-500 w-6 h-6" />
            </div>
            <h3 className="text-xl font-bold mb-2">Toplulukta Yayınla</h3>
            <p className="text-sm text-muted-foreground mb-4">Planını 'Keşfet' sayfasında yayınla ve diğer gezginlere yardımcı ol.</p>
          </div>
        </div>
      </div>
    </div>
  );
}
