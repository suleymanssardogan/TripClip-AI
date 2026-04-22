"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { CheckCircle, ArrowRight, Smartphone, Globe, Sparkles } from "lucide-react";

export default function WelcomePage() {
  const router = useRouter();
  const [email, setEmail] = useState("");

  useEffect(() => {
    const e = localStorage.getItem("email");
    if (!e) { router.push("/login"); return; }
    setEmail(e);
  }, [router]);

  return (
    <div className="min-h-screen bg-bg flex items-center justify-center px-6">
      {/* Orbs */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden">
        <div className="orb w-96 h-96 bg-neon top-1/4 -left-48" />
        <div className="orb w-80 h-80 bg-violet bottom-1/3 -right-40" />
      </div>

      <div className="relative w-full max-w-lg text-center">
        {/* Başarı ikonu */}
        <div className="w-20 h-20 bg-neon/10 border border-neon/20 rounded-full flex items-center justify-center mx-auto mb-6">
          <CheckCircle className="w-10 h-10 text-neon" />
        </div>

        <h1 className="font-display font-black text-3xl text-ice mb-2">
          Hoş Geldin! 🎉
        </h1>
        <p className="text-muted mb-2">
          Hesabın başarıyla oluşturuldu.
        </p>
        <p className="text-xs text-muted/60 bg-white/5 border border-white/10 rounded-lg px-4 py-2 inline-block mb-10">
          📧 {email}
        </p>

        {/* Adımlar */}
        <div className="glass rounded-2xl p-6 text-left mb-6 space-y-4">
          <p className="text-xs font-mono text-neon/60 uppercase tracking-widest mb-4">
            Nasıl Kullanırsın?
          </p>

          {[
            {
              icon: Smartphone,
              title: "iOS Uygulamasını İndir",
              desc: "Instagram veya kamera videonu yükle",
              color: "text-neon",
              bg: "bg-neon/10",
            },
            {
              icon: Sparkles,
              title: "AI Analiz Etsin",
              desc: "Mekanlar, kafeler, tarihi yerler otomatik çıkarılır",
              color: "text-violet",
              bg: "bg-violet/10",
            },
            {
              icon: Globe,
              title: "Rotanı Keşfet",
              desc: "Haritada gez, başkalarıyla paylaş",
              color: "text-coral",
              bg: "bg-coral/10",
            },
          ].map((step, i) => (
            <div key={i} className="flex items-center gap-4">
              <div className={`w-10 h-10 ${step.bg} rounded-xl flex items-center justify-center flex-shrink-0`}>
                <step.icon className={`w-5 h-5 ${step.color}`} />
              </div>
              <div>
                <p className="text-ice text-sm font-semibold">{step.title}</p>
                <p className="text-muted text-xs">{step.desc}</p>
              </div>
            </div>
          ))}
        </div>

        {/* Butonlar */}
        <div className="flex flex-col gap-3">
          <Link
            href="/dashboard"
            className="btn-primary py-3.5 rounded-xl font-bold text-sm flex items-center justify-center gap-2"
          >
            Dashboard'a Git <ArrowRight className="w-4 h-4" />
          </Link>
          <Link
            href="/explore"
            className="py-3.5 rounded-xl text-sm text-muted hover:text-ice border border-white/10 hover:border-white/20 transition-all"
          >
            Önce Gezileri Keşfet
          </Link>
        </div>
      </div>
    </div>
  );
}
