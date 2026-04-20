"use client";

import React, { useState } from "react";
import { motion } from "framer-motion";
import { 
  ChevronRight, 
  Sparkles, 
  Plus, 
  Trash2, 
  GripVertical, 
  Clock, 
  MapPin, 
  ArrowRight,
  BrainCircuit,
  Settings,
  Map as MapIcon
} from "lucide-react";
import Navbar from "@/components/Navbar";
import Link from "next/link";

const DAYS = [
  { id: "01", day: "Monday", title: "Arrival & Positano", active: true },
  { id: "02", day: "Tuesday", title: "Capri Waters", active: false },
  { id: "03", day: "Wednesday", title: "Ravello Heights", active: false },
];

const TIMELINE_EVENTS = [
  {
    id: 1,
    time: "09:00 AM",
    title: "Casa e Bottega",
    type: "Artisan Cafe & Design Shop",
    desc: "Start the day with fresh organic juices and healthy bowls. AI recommends this spot as it's the quietest before 10 AM.",
    image: "https://images.unsplash.com/photo-1540959733332-eab4deabeeaf?auto=format&fit=crop&q=80&w=400",
    transit: "5m Walk"
  },
  {
    id: 2,
    time: "12:30 PM",
    title: "Spiaggia Grande",
    type: "Iconic Beach & Seaside Dining",
    desc: "A lively beach scene with orange umbrellas. Reservation for lunch at Chez Black at 1:30 PM. AI Suggestion: Walk along the coastal path for photos.",
    image: "https://images.unsplash.com/photo-1533105079780-92b9be482077?auto=format&fit=crop&q=80&w=800",
    transit: "12m Transit"
  }
];

export default function EditorPage() {
  return (
    <div className="min-h-screen bg-surface font-body text-on-surface">
      <Navbar />
      
      <main className="max-w-screen-2xl mx-auto px-6 py-12 flex flex-col lg:flex-row gap-12 pt-32">
        {/* Left Column: Day Navigation & AI Widget */}
        <aside className="w-full lg:w-80 flex-shrink-0 flex flex-col gap-8">
          <div className="space-y-4">
            <span className="text-secondary font-headline text-xs font-black uppercase tracking-[0.3em]">Master Journey</span>
            <h2 className="text-5xl font-black text-white font-headline tracking-tighter leading-none">Amalfi Coast Editorial</h2>
            <p className="text-on-surface-variant text-sm leading-relaxed font-medium">Merging notes from Instagram, Lonely Planet, and personal AI curations into one seamless flow.</p>
          </div>

          <div className="flex flex-col gap-3">
             {DAYS.map(day => (
               <button 
                 key={day.id}
                 className={`flex items-center justify-between p-5 rounded-2xl transition-all ${day.active ? 'bg-secondary/10 border-l-4 border-secondary text-secondary' : 'bg-surface-container-high/50 hover:bg-surface-container-high text-on-surface-variant'}`}
               >
                 <div className="flex flex-col items-start">
                    <span className="text-[10px] uppercase tracking-widest font-black opacity-60">{day.day}</span>
                    <span className="font-black text-sm uppercase">{day.id}: {day.title}</span>
                 </div>
                 <ChevronRight className="w-4 h-4" />
               </button>
             ))}
          </div>

          {/* AI Optimizer Widget - High Contrast */}
          <div className="bg-surface-container-highest p-8 rounded-[2.5rem] relative overflow-hidden border border-white/5 shadow-2xl">
             <div className="absolute top-0 right-0 p-6 opacity-5">
                <BrainCircuit className="w-16 h-16 text-primary" />
             </div>
             <div className="relative z-10">
                <h4 className="font-headline font-black text-primary flex items-center gap-2 mb-4 tracking-tight">
                  <Sparkles className="w-5 h-5" />
                  AI Optimizer
                </h4>
                <p className="text-xs text-on-surface-variant leading-relaxed font-bold mb-6">
                  I've noticed your Day 1 cafes are on opposite ends of town. Toggle "Optimize" to re-order for the best sunset walk.
                </p>
                <button className="text-[10px] font-black uppercase tracking-[0.2em] text-secondary border-b-2 border-secondary/20 pb-1">Learn More</button>
             </div>
          </div>
        </aside>

        {/* Right Column: Timeline Editor */}
        <section className="flex-grow">
           <div className="flex items-center justify-between mb-12">
              <div className="flex items-center gap-6">
                 <div className="px-6 py-2 bg-primary text-on-primary rounded-full text-[10px] font-black uppercase tracking-[0.2em]">Editing Mode</div>
                 <span className="text-xs text-on-surface-variant font-bold italic opacity-40">Last synced 2m ago</span>
              </div>
              <button className="bg-secondary text-on-secondary px-8 py-4 rounded-full text-xs font-black uppercase tracking-[0.2em] flex items-center gap-2 hover:scale-[1.02] active:scale-95 transition-all shadow-xl shadow-secondary/20">
                <Plus className="w-4 h-4" />
                Add Stop
              </button>
           </div>

           <div className="relative space-y-12">
              <div className="absolute left-[22px] top-4 bottom-4 w-px bg-white/10 hidden lg:block" />

              {TIMELINE_EVENTS.map((event, i) => (
                <motion.div 
                  key={event.id}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.1 }}
                  className="relative flex flex-col lg:flex-row gap-8 items-start group"
                >
                  <div className={`absolute left-[14px] w-4 h-4 rounded-full border-4 border-surface z-10 hidden lg:block mt-8 transition-colors ${i === 0 ? 'bg-secondary' : 'bg-primary'}`} />

                  <div className="bg-surface-container-high rounded-[3rem] shadow-2xl overflow-hidden flex flex-col lg:flex-row w-full hover:border-white/10 transition-all duration-500 border border-white/5">
                    <div className="w-full lg:w-64 h-64 lg:h-auto overflow-hidden relative group">
                       <img src={event.image} className="w-full h-full object-cover transition-transform duration-700 group-hover:scale-110" alt={event.title} />
                       <div className="absolute top-6 left-6 bg-white text-primary px-4 py-2 rounded-2xl text-[10px] font-black uppercase tracking-widest shadow-2xl">
                         {event.time}
                       </div>
                    </div>

                    <div className="p-10 flex-grow flex flex-col">
                       <div className="flex justify-between items-start mb-6">
                          <div>
                             <h3 className="text-3xl font-black font-headline text-white tracking-tighter leading-none mb-3">{event.title}</h3>
                             <p className="text-primary font-black text-xs uppercase tracking-[0.2em]">{event.type}</p>
                          </div>
                          <div className="flex items-center gap-3 bg-black/20 p-2 rounded-full px-4">
                             <div className={`w-8 h-4 bg-surface-container-highest rounded-full relative p-1 cursor-pointer`}>
                                <div className={`w-2 h-2 rounded-full bg-white transition-all ${i === 0 ? 'translate-x-4 bg-secondary' : ''}`} />
                             </div>
                             <span className="text-[10px] font-black text-on-surface-variant uppercase tracking-[0.2em] hidden sm:inline">Optimize</span>
                          </div>
                       </div>
                       
                       <p className="text-on-surface-variant text-sm font-medium leading-relaxed max-w-lg mb-8">{event.desc}</p>
                       
                       <div className="mt-auto pt-8 border-t border-white/5 flex items-center justify-between">
                          <div className="flex -space-x-3">
                             <div className="w-10 h-10 rounded-full border-4 border-surface-container-high bg-primary text-on-primary flex items-center justify-center text-[10px] font-black shadow-xl">AI</div>
                             <div className="w-10 h-10 rounded-full border-4 border-surface-container-high bg-secondary text-on-secondary flex items-center justify-center text-[10px] font-black shadow-xl">IG</div>
                          </div>
                          <div className="flex gap-4">
                             <button className="text-on-surface-variant hover:text-white transition-colors"><GripVertical className="w-5 h-5" /></button>
                             <button className="text-on-surface-variant hover:text-secondary transition-colors"><Trash2 className="w-5 h-5" /></button>
                          </div>
                       </div>
                    </div>
                  </div>
                </motion.div>
              ))}
           </div>
        </section>
      </main>
    </div>
  );
}
