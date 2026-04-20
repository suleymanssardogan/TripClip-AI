"use client";

import React from "react";
import Navbar from "@/components/Navbar";
import { motion } from "framer-motion";
import { Map, List, Clock, CheckCircle2, ChevronRight, BarChart3, Globe2, Plus } from "lucide-react";
import Link from "next/link";

const USER_STATS = [
  { label: "Toplam Gezi", value: "12", icon: Map },
  { label: "Keşfedilen Mekan", value: "84", icon: List },
  { label: "Şehirler", value: "5", icon: Globe2 },
];

const MY_TRIPS = [
  {
    id: 1,
    title: "Antalya Yaz Tatili",
    status: "Completed",
    locations: 8,
    date: "20 Nis 2026",
    image: "https://images.unsplash.com/photo-1540959733332-eab4deabeeaf?auto=format&fit=crop&q=80&w=400"
  },
  {
    id: 2,
    title: "Paris Sanat Turu",
    status: "Processing",
    locations: 0,
    date: "19 Nis 2026",
    image: "https://images.unsplash.com/photo-1502602898657-3e91760cbb34?auto=format&fit=crop&q=80&w=400"
  },
  {
    id: 3,
    title: "Roma'nın Gizli Köşeleri",
    status: "Completed",
    locations: 12,
    date: "15 Nis 2026",
    image: "https://images.unsplash.com/photo-1552832230-c0197dd311b5?auto=format&fit=crop&q=80&w=400"
  }
];

export default function DashboardPage() {
  return (
    <div className="min-h-screen bg-background pb-20">
      <Navbar />
      
      <div className="pt-32 px-6 max-w-7xl mx-auto">
        <header className="flex flex-col md:flex-row md:items-center justify-between gap-6 mb-12">
          <div>
            <h1 className="text-4xl font-bold mb-2">Hoş geldin, Süleyman! 👋</h1>
            <p className="text-muted-foreground">Maceran kaldığı yerden devam ediyor.</p>
          </div>
          <button className="bg-primary text-white px-6 py-4 rounded-2xl font-bold flex items-center gap-2 hover:opacity-90 transition-opacity whitespace-nowrap">
            <Plus className="w-5 h-5" /> Yeni Gezi Oluştur
          </button>
        </header>

        {/* Stats Grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-12">
          {USER_STATS.map((stat, i) => (
            <motion.div 
              key={i} 
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.1 }}
              className="glass p-6 rounded-3xl border border-white/5"
            >
              <div className="flex items-center gap-4">
                <div className="w-12 h-12 rounded-2xl bg-primary/10 flex items-center justify-center">
                  <stat.icon className="text-primary w-6 h-6" />
                </div>
                <div>
                  <p className="text-xs text-muted-foreground uppercase font-bold tracking-wider">{stat.label}</p>
                  <p className="text-2xl font-bold">{stat.value}</p>
                </div>
              </div>
            </motion.div>
          ))}
        </div>

        {/* Trips Section */}
        <section>
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-2xl font-bold italic">Gezi Geçmişim</h2>
            <div className="flex gap-2">
              <button className="glass px-4 py-2 rounded-xl text-xs font-bold bg-white/5 transition-all">Tümü</button>
              <button className="glass px-4 py-2 rounded-xl text-xs font-bold hover:bg-white/5 transition-all">İşlenenler</button>
            </div>
          </div>

          <div className="space-y-4">
            {MY_TRIPS.map((trip, i) => (
              <motion.div 
                key={trip.id}
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.1 }}
                className="group glass p-4 rounded-3xl flex items-center gap-6 border border-white/5 hover:border-primary/30 transition-all cursor-pointer"
              >
                <div className="w-24 h-24 rounded-2xl overflow-hidden relative flex-shrink-0">
                  <img src={trip.image} className="w-full h-full object-cover group-hover:scale-110 transition-transform duration-500" alt={trip.title} />
                  {trip.status === "Processing" && (
                    <div className="absolute inset-0 bg-black/60 flex items-center justify-center">
                      <Clock className="w-6 h-6 text-primary animate-spin" />
                    </div>
                  )}
                </div>
                
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <h3 className="font-bold text-lg">{trip.title}</h3>
                    {trip.status === "Completed" && <CheckCircle2 className="w-4 h-4 text-emerald-500" />}
                  </div>
                  <div className="flex items-center gap-4 text-xs text-muted-foreground">
                    <span className="flex items-center gap-1"><Map className="w-3 h-3" /> {trip.locations} Lokasyon</span>
                    <span className="flex items-center gap-1"><Clock className="w-3 h-3" /> {trip.date}</span>
                  </div>
                </div>

                <div className="flex items-center gap-2 pr-4">
                  <span className={`text-[10px] font-bold px-3 py-1 rounded-full uppercase ${trip.status === "Completed" ? "bg-emerald-500/10 text-emerald-500" : "bg-primary/10 text-primary"}`}>
                    {trip.status === "Completed" ? "Tamamlandı" : "İşleniyor"}
                  </span>
                  <ChevronRight className="w-5 h-5 text-muted-foreground group-hover:text-primary transition-colors" />
                </div>
              </motion.div>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
