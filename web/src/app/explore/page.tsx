"use client";

import React from "react";
import { motion } from "framer-motion";
import { 
  Search, 
  Sparkles, 
  TrendingUp, 
  ArrowRight, 
  PlusCircle, 
  Map as MapIcon, 
  Users, 
  Clapperboard, 
  CalendarDays,
  Heart,
  PlayCircle
} from "lucide-react";
import Navbar from "@/components/Navbar";
import MapPreview from "@/components/MapPreview";

const TRENDING_REELS = [
  {
    id: 1,
    title: "Mermerli Beach Secrets",
    user: "@VoyageVibes",
    views: "12k",
    image: "https://images.unsplash.com/photo-1540959733332-eab4deabeeaf?auto=format&fit=crop&q=80&w=400",
    tag: "#1 Trending"
  },
  {
    id: 2,
    title: "Hidden Roastery in Kaleici",
    user: "@BeanFinder",
    views: "8.4k",
    image: "https://images.unsplash.com/photo-1552832230-c0197dd311b5?auto=format&fit=crop&q=80&w=400",
    tag: "Top Coffee"
  },
  {
    id: 3,
    title: "Sunset at Apollo's Temple",
    user: "@HistoryHunter",
    views: "15k",
    image: "https://images.unsplash.com/photo-1502602898657-3e91760cbb34?auto=format&fit=crop&q=80&w=400",
    tag: "History"
  },
  {
    id: 4,
    title: "Old Bazaar Gem Hunt",
    user: "@CuratedStay",
    views: "6.2k",
    image: "https://images.unsplash.com/photo-1552832230-c0197dd311b5?auto=format&fit=crop&q=80&w=400",
    tag: "Shopping"
  }
];

export default function ExplorePage() {
  return (
    <div className="min-h-screen bg-surface font-body text-on-surface selection:bg-secondary-container selection:text-on-secondary-container">
      <Navbar />
      
      <main className="pt-20 pb-32">
        {/* Interactive Map Hero */}
        <section className="relative h-[618px] w-full overflow-hidden">
           <MapPreview />
           
           {/* Floating Search/AI Panel */}
           <div className="absolute top-10 left-1/2 -translate-x-1/2 z-[1000] w-full max-w-2xl px-6">
              <div className="bg-surface-container-high/80 dark:bg-surface-container-highest/80 backdrop-blur-2xl rounded-full p-2 shadow-[0_20px_50px_-12px_rgba(0,51,49,0.15)] flex items-center gap-2 border border-white/5">
                <div className="pl-4 flex items-center gap-3 flex-1">
                  <Search className="text-on-surface-variant w-5 h-5 opacity-60" />
                  <input 
                    className="bg-transparent border-none focus:ring-0 text-on-surface w-full font-medium placeholder:text-outline-variant/60 outline-none" 
                    placeholder="Explore Antalya's hidden gems..." 
                    type="text"
                  />
                </div>
                <button className="bg-secondary hover:bg-on-secondary-fixed-variant text-on-secondary px-6 py-2.5 rounded-full font-bold transition-all flex items-center gap-2 active:scale-95">
                  <Sparkles className="w-4 h-4" />
                  AI Insight
                </button>
              </div>
           </div>
        </section>

        {/* Live City Guides Section */}
        <section className="-mt-32 relative z-[1001] px-6 max-w-screen-2xl mx-auto">
          <div className="flex justify-between items-end mb-8">
            <div>
              <div className="flex items-center gap-2 text-secondary font-bold text-xs uppercase tracking-[0.2em] mb-2 font-headline">
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-secondary opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-secondary"></span>
                </span>
                Live Now in Antalya
              </div>
              <h2 className="text-4xl font-black tracking-tighter font-headline">Live City Guides</h2>
            </div>
            <button className="text-primary-fixed-dim font-bold flex items-center gap-2 hover:gap-3 transition-all group">
              View All Spots
              <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
            </button>
          </div>

          {/* Horizontal/Asymmetric Feed */}
          <div className="flex gap-8 pb-12 overflow-x-auto no-scrollbar pt-6">
            {TRENDING_REELS.map((reel, i) => (
              <motion.div 
                key={reel.id}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.1 }}
                className={`relative min-w-[280px] aspect-[9/16] rounded-3xl overflow-hidden shadow-2xl group cursor-pointer ${i % 2 === 1 ? 'translate-y-6' : ''}`}
              >
                <img src={reel.image} className="absolute inset-0 w-full h-full object-cover transition-transform duration-700 group-hover:scale-110" alt={reel.title} />
                <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-black/30 flex flex-col justify-between p-6">
                  <div className="flex justify-between items-start">
                    <span className="bg-white/20 backdrop-blur-md px-3 py-1 rounded-full text-[10px] font-bold text-white uppercase tracking-wider border border-white/10">
                      {reel.tag}
                    </span>
                    <Heart className="text-white/80 w-5 h-5" />
                  </div>
                  <div>
                    <h3 className="text-white font-bold text-lg leading-tight mb-1">{reel.title}</h3>
                    <p className="text-white/70 text-xs font-medium">{reel.user} • {reel.views} views</p>
                  </div>
                </div>
              </motion.div>
            ))}
          </div>
        </section>

        {/* Community Stat Cards */}
        <section className="max-w-screen-2xl mx-auto px-6 grid grid-cols-1 md:grid-cols-12 gap-8 mt-12">
          <div className="md:col-span-8 bg-surface-container-low rounded-[40px] p-10 flex flex-col justify-center relative overflow-hidden group border border-white/5">
             <div className="relative z-10">
                <h4 className="text-3xl font-black mb-3 font-headline">Collective Wisdom</h4>
                <p className="text-on-surface-variant max-w-md mb-8 leading-relaxed opacity-80">
                  Join 4,200 other explorers currently documenting Antalya. Your contributions power the AI insights for the next traveler.
                </p>
                <button className="bg-primary-container text-on-primary-container px-8 py-4 rounded-full font-bold inline-flex items-center gap-2 hover:opacity-90 transition-all">
                  Contribute a Clip
                  <PlusCircle className="w-5 h-5" />
                </button>
             </div>
             
             {/* Abstract Neural Mesh Background (Placeholder with CSS) */}
             <div className="absolute right-[-10%] top-[-10%] w-[300px] h-[300px] bg-primary/10 rounded-full blur-[100px] pointer-events-none" />
          </div>

          <div className="md:col-span-4 bg-secondary text-on-secondary rounded-[40px] p-10 flex flex-col justify-between shadow-2xl relative overflow-hidden">
             <div className="relative z-10">
                <TrendingUp className="w-10 h-10 mb-6 opacity-30" />
                <h4 className="text-3xl font-black font-headline leading-tight">Trending Destinations</h4>
             </div>
             <div className="mt-8 space-y-6 relative z-10">
                {[
                  { name: "Olympos", growth: "+42%" },
                  { name: "Kas Harbor", growth: "+18%" },
                  { name: "Perge Ruins", growth: "+5%" }
                ].map((item, i) => (
                  <div key={i} className="flex justify-between items-center border-b border-white/10 pb-3">
                    <span className="font-bold">{item.name}</span>
                    <span className="text-xs bg-white/20 px-3 py-1 rounded-full">{item.growth}</span>
                  </div>
                ))}
             </div>
          </div>
        </section>
      </main>

      {/* Floating Action Button */}
      <button className="fixed bottom-10 right-10 w-16 h-16 bg-secondary text-on-secondary rounded-full flex items-center justify-center shadow-2xl z-50 active:scale-90 transition-transform hover:scale-105">
        <PlayCircle className="w-8 h-8 fill-current" />
      </button>
    </div>
  );
}
