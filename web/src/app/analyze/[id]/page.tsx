"use client";

import React, { useState } from "react";
import { motion } from "framer-motion";
import { 
  MapPin, 
  Sparkles, 
  ArrowLeft, 
  Clock, 
  DollarSign, 
  Utensils, 
  ArrowRight, 
  BrainCircuit,
} from "lucide-react";
import Navbar from "@/components/Navbar";
import { useRouter } from "next/navigation";

const MOCK_ANALYSIS = {
  locations: [
    {
      id: "01",
      name: "Spiaggia Grande",
      desc: "The main beach of Positano, identified by the iconic orange umbrellas and the cliffside church background.",
      image: "https://images.unsplash.com/photo-1512343879784-a960bf40e7f2?auto=format&fit=crop&q=80&w=800",
      bestTime: "10 AM",
      price: "Free Entry",
      category: "Beach"
    },
    {
      id: "02",
      name: "Villa Treville Gardens",
      desc: "Private terrace appearing in the reel's middle segment. Requires reservation for the cocktail lounge.",
      image: "https://images.unsplash.com/photo-1548126466-41999a552014?auto=format&fit=crop&q=80&w=800",
      bestTime: "Sunset",
      price: "Dining Spot",
      category: "Luxury"
    }
  ]
};

export default function AnalysisResultPage() {
  const router = useRouter();
  const [added, setAdded] = useState(false);

  return (
    <div className="min-h-screen relative overflow-hidden bg-surface font-body text-on-surface">
      <Navbar />
      
      {/* Background Blobs */}
      <div className="mesh-blob w-[600px] h-[600px] bg-primary/10 -top-40 -left-40" />
      <div className="mesh-blob w-[400px] h-[400px] bg-secondary/5 top-1/4 -right-20" />

      <main className="pt-32 pb-32 px-6 max-w-screen-xl mx-auto relative z-10">
        <button onClick={() => router.back()} className="flex items-center gap-2 text-on-surface-variant hover:text-white transition-all mb-12 group font-bold uppercase tracking-widest text-[10px]">
          <ArrowLeft className="w-4 h-4 group-hover:-translate-x-1 transition-transform" /> Back to Dashboard
        </button>

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-10">
          {/* AI Insights - LG 4 */}
          <div className="lg:col-span-4 space-y-8">
            <motion.div 
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              className="bg-surface-container-highest/60 backdrop-blur-3xl p-10 rounded-[3rem] relative overflow-hidden border border-white/10 shadow-2xl"
            >
              <div className="absolute -right-6 -top-6 opacity-10">
                <BrainCircuit className="w-32 h-32 text-primary" />
              </div>
              <div className="relative z-10 text-left">
                <span className="bg-secondary/20 text-secondary px-4 py-1.5 rounded-full text-[10px] font-black uppercase tracking-[0.2em] inline-block mb-6">
                   Deep Vision AI
                </span>
                <h3 className="font-headline text-3xl font-black mb-6 tracking-tighter">Analysis Insights</h3>
                <p className="text-on-surface-variant leading-relaxed text-sm font-medium opacity-80 mb-8">
                  Detected <span className="text-primary font-bold">3 hotspots</span> and <span className="text-primary font-bold">2 transit routes</span>. The vibe is Mediterranean Luxury.
                </p>
                <div className="flex flex-wrap gap-2">
                  {["#HiddenGem", "#Luxury", "#Italy"].map(tag => (
                    <span key={tag} className="bg-white/5 border border-white/10 text-on-surface-variant px-4 py-2 rounded-xl text-[10px] font-bold">
                      {tag}
                    </span>
                  ))}
                </div>
              </div>
            </motion.div>

            <motion.div 
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.2 }}
              className="bg-secondary p-10 rounded-[3rem] text-on-secondary text-center shadow-2xl shadow-secondary/20"
            >
               <h4 className="font-headline text-2xl font-black mb-3">Add to Plan?</h4>
               <p className="text-on-secondary/70 text-sm mb-8 font-medium italic">Save this curated route to your journeys.</p>
               <button 
                 onClick={() => setAdded(true)}
                 className="w-full bg-on-secondary text-secondary py-5 rounded-full font-black flex items-center justify-center gap-3 hover:scale-[1.03] active:scale-95 transition-all text-sm uppercase tracking-widest"
               >
                 {added ? "Success! ✅" : "Save Route"}
                 {!added && <ArrowRight className="w-5 h-5" />}
               </button>
            </motion.div>
          </div>

          {/* Route Preview - LG 8 */}
          <div className="lg:col-span-8 space-y-12">
            <div className="flex items-end justify-between px-6">
              <h2 className="font-headline text-4xl font-black tracking-tighter">Journey Map</h2>
              <span className="text-secondary font-black text-xs uppercase tracking-[0.3em] opacity-60">Verified Route</span>
            </div>

            <div className="space-y-12">
              {MOCK_ANALYSIS.locations.map((loc, i) => (
                <motion.div 
                  key={loc.id}
                  initial={{ opacity: 0, y: 30 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.2 }}
                  className={`glass-card rounded-[3.5rem] flex flex-col md:flex-row overflow-hidden ${i % 2 === 1 ? 'md:flex-row-reverse md:translate-x-12' : ''}`}
                >
                  <div className="md:w-5/12 h-80 md:h-[450px] overflow-hidden">
                    <img src={loc.image} className="w-full h-full object-cover transition-transform duration-1000 hover:scale-110" alt={loc.name} />
                  </div>
                  <div className={`md:w-7/12 p-12 flex flex-col justify-center ${i % 2 === 1 ? 'text-right items-end' : ''}`}>
                    <span className="text-secondary font-black text-xs uppercase tracking-[0.4em] mb-6 block">Stop {loc.id}</span>
                    <h3 className="font-headline text-4xl font-black text-on-surface mb-6 tracking-tighter leading-none">{loc.name}</h3>
                    <p className="text-on-surface-variant text-sm leading-[1.7] mb-10 opacity-70 font-medium max-w-sm">
                      {loc.desc}
                    </p>
                    <div className={`flex gap-8 ${i % 2 === 1 ? 'justify-end' : ''}`}>
                      <div className="flex items-center gap-3 text-on-surface-variant">
                        <Clock className="w-5 h-5 text-secondary" />
                        <span className="text-xs font-black uppercase tracking-widest">{loc.bestTime}</span>
                      </div>
                      <div className="flex items-center gap-3 text-on-surface-variant">
                        <DollarSign className="w-5 h-5 text-secondary" />
                        <span className="text-xs font-black uppercase tracking-widest">{loc.price}</span>
                      </div>
                    </div>
                  </div>
                </motion.div>
              ))}
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
