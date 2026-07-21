"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { motion } from "framer-motion";
import { CheckCircle, ArrowRight, Smartphone, Globe, Sparkles } from "lucide-react";

export default function WelcomePage() {
  const router = useRouter();
  const [email, setEmail] = useState("");

  useEffect(() => {
    const e = localStorage.getItem("email");
    if (!e) { router.push("/login"); return; }
    setTimeout(() => {
      setEmail(e);
    }, 0);
  }, [router]);

  return (
    <div className="min-h-screen bg-bg flex items-center justify-center px-6">
      <motion.div
        initial={{ opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: "easeOut" }}
        className="relative w-full max-w-lg text-center"
      >
        {/* Başarı ikonu */}
        <motion.div
          initial={{ opacity: 0, scale: 0.7 }} animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.4, delay: 0.1, ease: "easeOut" }}
          className="w-20 h-20 bg-success/10 border border-success/25 rounded-full flex items-center justify-center mx-auto mb-6"
        >
          <CheckCircle className="w-10 h-10 text-success" />
        </motion.div>

        <motion.h1
          initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.15 }}
          className="font-display font-black text-3xl text-text mb-2"
        >
          Hoş Geldin!
        </motion.h1>
        <motion.p
          initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="text-text-secondary mb-2"
        >
          Hesabın başarıyla oluşturuldu.
        </motion.p>
        <motion.p
          initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.25 }}
          className="font-mono text-xs text-text-tertiary bg-surface border border-border rounded-md px-4 py-2 inline-block mb-10"
        >
          {email}
        </motion.p>

        {/* Adımlar */}
        <div className="bg-surface border border-border rounded-lg p-6 text-left mb-6 space-y-4">
          <p className="font-mono text-xs text-text-tertiary uppercase tracking-widest mb-4">
            Nasıl Kullanırsın?
          </p>

          {[
            {
              icon: Smartphone,
              title: "iOS Uygulamasını İndir",
              desc: "Instagram veya kamera videonu yükle",
            },
            {
              icon: Sparkles,
              title: "AI Analiz Etsin",
              desc: "Mekanlar, kafeler, tarihi yerler otomatik çıkarılır",
            },
            {
              icon: Globe,
              title: "Rotanı Keşfet",
              desc: "Haritada gez, başkalarıyla paylaş",
            },
          ].map((step, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, x: -12 }} animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.3 + i * 0.1 }}
              className="flex items-center gap-4"
            >
              <div className="w-10 h-10 bg-accent/10 border border-accent/20 rounded-md flex items-center justify-center flex-shrink-0">
                <step.icon className="w-5 h-5 text-accent-text" />
              </div>
              <div>
                <p className="text-text text-sm font-semibold">{step.title}</p>
                <p className="text-text-tertiary text-xs">{step.desc}</p>
              </div>
            </motion.div>
          ))}
        </div>

        {/* Butonlar */}
        <motion.div
          initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.65 }}
          className="flex flex-col gap-3"
        >
          <Link
            href="/dashboard"
            className="bg-accent text-on-accent hover:bg-accent-hover transition-colors py-3.5 rounded-md font-bold text-sm flex items-center justify-center gap-2"
          >
            Dashboard&apos;a Git <ArrowRight className="w-4 h-4" />
          </Link>
          <Link
            href="/explore"
            className="py-3.5 rounded-md text-sm text-text-secondary hover:text-text border border-border-strong hover:border-border-strong transition-all"
          >
            Önce Gezileri Keşfet
          </Link>
        </motion.div>
      </motion.div>
    </div>
  );
}
