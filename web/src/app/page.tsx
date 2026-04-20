"use client";

import React from "react";
import { motion } from "framer-motion";
import { Link as LinkIcon, Sparkles, Compass, Users, TrendingUp, ChevronRight } from "lucide-react";
import Navbar from "@/components/Navbar";
import { useRouter } from "next/navigation";

export default function Home() {
  const router = useRouter();

  const handleAnalyze = (e: React.FormEvent) => {
    e.preventDefault();
    router.push("/analyze/test");
  };

  return (
    <div className="min-h-screen relative overflow-hidden bg-surface font-body text-on-surface">
      <Navbar />
      
      {/* Premium Background Elements */}
      <div className="mesh-blob w-[500px] h-[500px] bg-primary/20 -top-20 -left-20" />
      <div className="mesh-blob w-[400px] h-[400px] bg-secondary/10 top-1/2 -right-20" />
      
      <main className="pt-32 pb-32 px-6 max-w-screen-xl mx-auto relative z-10">
        {/* Animated Hero Section */}
        <section className="mb-24">
          <motion.div 
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.8, ease: "easeOut" }}
            className="relative overflow-hidden rounded-[3rem] bg-surface-container-lowest/40 backdrop-blur-3xl p-12 md:p-20 border border-white/10 shadow-[0_40px_100px_-20px_rgba(0,0,0,0.5)]"
          >
            <div className="relative z-10 max-w-3xl">
              <motion.span 
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.3 }}
                className="font-headline text-secondary font-black uppercase tracking-[0.3em] text-xs mb-6 block"
              >
                AI Visual Curator
              </motion.span>
              
              <motion.h1 
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.4 }}
                className="font-headline text-5xl md:text-8xl font-black tracking-tighter mb-10 leading-[0.9] text-on-surface"
              >
                Turn Reels into <br/>
                <span className="text-transparent bg-clip-text bg-gradient-to-r from-secondary to-orange-400 italic">Magic Trips.</span>
              </motion.h1>
              
              <motion.form 
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.5 }}
                onSubmit={handleAnalyze} 
                className="flex flex-col md:flex-row gap-4 p-2 bg-white/[0.03] backdrop-blur-md rounded-[2.5rem] border border-white/5 shadow-inner"
              >
                <div className="flex-grow relative flex items-center px-6">
                  <LinkIcon className="text-secondary w-5 h-5 mr-4" />
                  <input 
                    className="w-full bg-transparent border-none py-5 text-on-surface placeholder:text-on-surface-variant/40 focus:ring-0 outline-none font-medium" 
                    placeholder="Paste Reels URL here..." 
                    type="text"
                    required
                  />
                </div>
                <button 
                  type="submit"
                  className="bg-secondary text-on-secondary px-12 py-5 rounded-full font-headline font-black hover:bg-secondary/90 hover:scale-[1.02] active:scale-95 transition-all shadow-2xl shadow-secondary/20 flex items-center justify-center gap-3 group"
                >
                  Start Analysis
                  <Sparkles className="w-5 h-5 group-hover:rotate-12 transition-transform" />
                </button>
              </motion.form>
            </div>
          </motion.div>
        </section>

        {/* Feature Grid with Hover Effects */}
        <div className="grid md:grid-cols-3 gap-8">
           {[
             { title: "AI Vision Extract", desc: "Our models identify coordinates and vibes from pixels alone.", icon: Compass, color: "text-primary-fixed-dim" },
             { title: "Collective hub", desc: "Sync your maps with 4,200+ explorers worldwide.", icon: Users, color: "text-secondary" },
             { title: "Master Planner", desc: "A cinematic timeline editor for your editorial journey.", icon: TrendingUp, color: "text-tertiary-fixed-dim" }
           ].map((feature, i) => (
             <motion.div 
               key={i}
               initial={{ opacity: 0, y: 30 }}
               animate={{ opacity: 1, y: 0 }}
               transition={{ delay: 0.6 + (i * 0.1) }}
               className="glass-card p-10 rounded-[2.5rem] group"
             >
                <div className={`w-14 h-14 rounded-2xl bg-white/5 flex items-center justify-center mb-8 group-hover:scale-110 transition-transform`}>
                   <feature.icon className={`${feature.color} w-7 h-7`} />
                </div>
                <h3 className="font-headline text-2xl font-black mb-4 tracking-tight">{feature.title}</h3>
                <p className="text-on-surface-variant font-medium opacity-60 leading-relaxed">{feature.desc}</p>
                <div className="mt-8 flex items-center text-xs font-black uppercase tracking-widest text-secondary opacity-0 group-hover:opacity-100 transition-opacity">
                   Explore More <ChevronRight className="w-4 h-4 ml-1" />
                </div>
             </motion.div>
           ))}
        </div>
      </main>
    </div>
  );
}
