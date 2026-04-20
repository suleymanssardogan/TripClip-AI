"use client";

import React from "react";
import { motion } from "framer-motion";
import { 
  Map as MapIcon, 
  Share2, 
  Users, 
  BrainCircuit, 
  Star, 
  Sun, 
  Utensils, 
  MapPin, 
  Lightbulb,
  ExternalLink
} from "lucide-react";
import Navbar from "@/components/Navbar";

const STATS = [
  { label: "Total Spots", value: "12" },
  { label: "Distance", value: "42km" },
  { label: "Duration", value: "7 Days" },
  { label: "Cities", value: "3" },
];

const COLLABORATORS = [
  { name: "Sarah", img: "https://images.unsplash.com/photo-1494790108377-be9c29b29330?auto=format&fit=crop&q=80&w=150" },
  { name: "James", img: "https://images.unsplash.com/photo-1599566150163-29194dcaad36?auto=format&fit=crop&q=80&w=150" },
  { name: "Mark", img: "https://images.unsplash.com/photo-1535713875002-d1d0cf377fde?auto=format&fit=crop&q=80&w=150" },
];

export default function SharePage() {
  return (
    <div className="min-h-screen bg-surface font-body text-on-surface">
      <Navbar />
      
      <main className="max-w-screen-2xl mx-auto px-6 pb-32 pt-24">
        {/* Hero Section: Cinematic Depth */}
        <section className="relative w-full h-[530px] rounded-[3rem] overflow-hidden mb-12 shadow-2xl group">
          <img 
            src="https://images.unsplash.com/photo-1533105079780-92b9be482077?auto=format&fit=crop&q=80&w=1200" 
            className="w-full h-full object-cover transition-transform duration-1000 group-hover:scale-105" 
            alt="Amalfi Coast" 
          />
          <div className="absolute inset-0 bg-gradient-to-t from-primary/95 via-primary/20 to-transparent"></div>
          
          <div className="absolute bottom-0 left-0 p-12 w-full flex flex-col md:flex-row md:items-end justify-between gap-8">
            <motion.div 
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              className="max-w-3xl"
            >
              <span className="inline-block px-4 py-2 bg-secondary text-on-secondary rounded-full text-xs font-bold uppercase tracking-[0.2em] mb-6 shadow-lg shadow-secondary/20">
                Summer Journey 2024
              </span>
              <h1 className="text-5xl md:text-7xl font-black text-on-primary font-headline tracking-tighter leading-none mb-6">
                The Mediterranean Dream: <br/>Amalfi & Beyond
              </h1>
              <p className="text-on-primary/80 text-xl leading-relaxed max-w-xl opacity-90">
                A curated exploration through coastal lemon groves, hidden grottoes, and the timeless elegance of Positano.
              </p>
            </motion.div>

            <div className="flex flex-wrap gap-4 relative z-10">
              <button className="bg-secondary text-on-secondary px-10 py-5 rounded-full font-bold shadow-xl flex items-center gap-3 transition-all hover:scale-105 active:scale-95 shadow-secondary/20">
                <MapIcon className="w-5 h-5" /> Open in Google Maps
              </button>
              <button className="bg-white/10 backdrop-blur-xl border border-white/20 text-on-primary px-10 py-5 rounded-full font-bold flex items-center gap-3 transition-all hover:bg-white/20">
                <Share2 className="w-5 h-5" /> Share Private Link
              </button>
            </div>
          </div>
        </section>

        {/* Content Grid: Asymmetric Layout */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-12">
          
          {/* Main Content (Left) */}
          <div className="lg:col-span-8 space-y-16">
            
            {/* Stats Bento */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
              {STATS.map((stat, i) => (
                <div key={i} className="bg-surface-container-low p-8 rounded-[2rem] flex flex-col items-center justify-center text-center border border-white/5">
                  <span className="text-secondary font-black text-4xl mb-2">{stat.value}</span>
                  <span className="text-on-surface-variant font-bold text-[10px] uppercase tracking-widest opacity-60">{stat.label}</span>
                </div>
              ))}
            </div>

            {/* Collaborative Section */}
            <div className="bg-surface-container-lowest p-12 rounded-[3rem] shadow-[0_20px_50px_-12px_rgba(0,51,49,0.06)] relative overflow-hidden border border-white/5">
              <div className="absolute top-0 right-0 w-48 h-48 bg-secondary/5 rounded-bl-full -mr-16 -mt-16 opacity-50"></div>
              <div className="relative z-10">
                <h3 className="text-3xl font-black font-headline mb-8 text-primary flex items-center gap-4 tracking-tighter">
                  <Users className="text-secondary w-8 h-8" /> Trip Collaborators
                </h3>
                <div className="flex flex-wrap items-center gap-8 mb-10">
                  <div className="flex -space-x-5">
                    {COLLABORATORS.map((collab, i) => (
                      <img 
                        key={i} 
                        src={collab.img} 
                        className="w-20 h-20 rounded-full border-[6px] border-surface shadow-xl" 
                        alt={collab.name} 
                      />
                    ))}
                    <div className="w-20 h-20 rounded-full border-[6px] border-surface bg-surface-container-high flex items-center justify-center text-primary font-black text-xl shadow-xl">
                      +4
                    </div>
                  </div>
                  <div>
                    <p className="font-black text-2xl text-primary tracking-tighter">Alex, Sarah, James and 4 others</p>
                    <p className="text-on-surface-variant font-medium opacity-60">Editing access enabled for this trip</p>
                  </div>
                </div>
                <button className="bg-surface-container-high hover:bg-primary hover:text-white text-primary font-bold px-8 py-4 rounded-2xl flex items-center gap-3 transition-all text-sm">
                  <Share2 className="w-4 h-4" /> Invite Friends
                </button>
              </div>
            </div>

            {/* Video Highlights (Editorial Style) */}
            <div className="space-y-10">
              <h3 className="text-4xl font-black font-headline text-primary tracking-tighter italic">Cinematic Moments</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-10">
                <div className="group relative rounded-[2.5rem] overflow-hidden shadow-2xl translate-y-12 transition-transform duration-500 hover:translate-y-8">
                  <img src="https://images.unsplash.com/photo-1523906834658-6e24ef2386f9?auto=format&fit=crop&q=80&w=400" className="w-full aspect-[4/5] object-cover transition-transform duration-700 group-hover:scale-110" alt="Moment 1" />
                  <div className="absolute inset-0 bg-gradient-to-t from-primary/90 via-transparent to-transparent flex items-end p-10">
                    <div>
                      <span className="text-secondary text-xs font-black uppercase tracking-widest mb-3 block">Day 1: Arrival</span>
                      <h4 className="text-on-primary text-2xl font-black font-headline tracking-tight">The Hidden Alleys of Naples</h4>
                    </div>
                  </div>
                </div>
                <div className="group relative rounded-[2.5rem] overflow-hidden shadow-2xl transition-transform duration-500 hover:-translate-y-2">
                  <img src="https://images.unsplash.com/photo-1548126466-41999a552014?auto=format&fit=crop&q=80&w=400" className="w-full aspect-[4/5] object-cover transition-transform duration-700 group-hover:scale-110" alt="Moment 2" />
                  <div className="absolute inset-0 bg-gradient-to-t from-primary/90 via-transparent to-transparent flex items-end p-10">
                    <div>
                      <span className="text-secondary text-xs font-black uppercase tracking-widest mb-3 block">Day 3: Coastal</span>
                      <h4 className="text-on-primary text-2xl font-black font-headline tracking-tight">Private Grotto Expedition</h4>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* AI Insights (Right) */}
          <aside className="lg:col-span-4 space-y-8">
            <div className="bg-primary text-on-primary p-10 rounded-[3rem] shadow-2xl relative overflow-hidden">
               <div className="absolute inset-0 opacity-10 pointer-events-none" style={{ backgroundImage: 'radial-gradient(#ffffff 1px, transparent 1px)', backgroundSize: '30px 30px' }} />
               <div className="relative z-10">
                  <div className="flex items-center gap-3 mb-8">
                    <BrainCircuit className="text-primary-fixed-dim w-8 h-8" />
                    <h3 className="text-lg font-black font-headline uppercase tracking-[0.2em] text-primary-fixed-dim">AI Trip Insights</h3>
                  </div>
                  <ul className="space-y-8">
                    <li className="flex gap-5">
                      <Star className="text-secondary w-6 h-6 shrink-0 mt-1 fill-current" />
                      <p className="text-on-primary/80 text-sm leading-relaxed font-medium">Optimization: Travel time between Amalfi and Positano is best scheduled for 10 AM to avoid the tour bus rush.</p>
                    </li>
                    <li className="flex gap-5">
                      <Sun className="text-secondary w-6 h-6 shrink-0 mt-1" />
                      <p className="text-on-primary/80 text-sm leading-relaxed font-medium">Climate Alert: High UV expected on Day 4. We've added shaded terrace stops to your afternoon route.</p>
                    </li>
                    <li className="flex gap-5">
                      <Utensils className="text-secondary w-6 h-6 shrink-0 mt-1" />
                      <p className="text-on-primary/80 text-sm leading-relaxed font-medium">Curation: 4 Michelin-recommended spots identified within 500m of your evening walking route.</p>
                    </li>
                  </ul>
               </div>
            </div>

            <div className="bg-surface-container-low rounded-[3rem] overflow-hidden p-3 group border border-white/5">
                <div className="rounded-[2.5rem] overflow-hidden h-96 relative shadow-inner">
                   <img src="https://images.unsplash.com/photo-1548126466-41999a552014?auto=format&fit=crop&q=80&w=400" className="w-full h-full object-cover grayscale opacity-40 group-hover:grayscale-0 group-hover:opacity-100 transition-all duration-700" alt="Map" />
                   <div className="absolute inset-0 bg-primary/20 mix-blend-multiply" />
                   <div className="absolute inset-0 flex items-center justify-center">
                      <div className="bg-surface/90 backdrop-blur-md p-4 rounded-2xl shadow-2xl border border-white/10">
                        <MapPin className="text-secondary w-6 h-6 animate-bounce" />
                      </div>
                   </div>
                </div>
                <div className="p-8">
                   <h4 className="font-black text-2xl text-primary mb-3 tracking-tighter">Interactive Journey Map</h4>
                   <p className="text-sm text-on-surface-variant mb-8 opacity-70">Explore every waypoint and customized route detail in full screen.</p>
                   <button className="w-full py-5 border-2 border-primary/10 text-primary font-black rounded-[1.5rem] hover:bg-primary hover:text-white transition-all text-sm uppercase tracking-widest">
                      View Full Map
                   </button>
                </div>
            </div>

            {/* Community Tip */}
            <div className="bg-surface-container-lowest p-8 rounded-[2.5rem] border border-white/5 flex items-center gap-5 cursor-pointer hover:bg-surface-container-low transition-all">
               <div className="w-14 h-14 rounded-2xl bg-secondary/10 flex items-center justify-center text-secondary shadow-inner">
                  <Lightbulb className="w-6 h-6" />
               </div>
               <div>
                  <p className="font-black text-primary text-lg tracking-tight">Pro Tip: Lemon Gelato</p>
                  <p className="text-xs text-on-surface-variant opacity-70 font-medium">Try the stand near St. Andrew's Cathedral.</p>
               </div>
            </div>
          </aside>
        </div>
      </main>
    </div>
  );
}
