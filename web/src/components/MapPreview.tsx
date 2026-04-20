"use client";

import { MapPin, Navigation, Info, ExternalLink } from "lucide-react";
import { useEffect, useState } from "react";
import "leaflet/dist/leaflet.css";

// Leaflet uses 'window', so we must import it dynamically or check for window
let MapContainer: any, TileLayer: any, Marker: any, Popup: any, L: any;

const MOCK_POINTS = [
  { lat: 36.8853, lng: 30.7082, title: "Hadrian Kapısı", category: "Landmark" },
  { lat: 36.8530, lng: 30.8037, title: "Lara Plajı", category: "Beach" },
  { lat: 36.8840, lng: 30.7040, title: "Kaleiçi", category: "District" },
  { lat: 36.8524, lng: 30.7831, title: "Düden Şelalesi", category: "Nature" },
];

export default function MapPreview() {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    // Dynamic imports to prevent SSR errors
    const Leaflet = require("react-leaflet");
    const LeafletLib = require("leaflet");
    MapContainer = Leaflet.MapContainer;
    TileLayer = Leaflet.TileLayer;
    Marker = Leaflet.Marker;
    Popup = Leaflet.Popup;
    L = LeafletLib;

    // Fix for missing marker icons in Leaflet + Next.js
    delete L.Icon.Default.prototype._getIconUrl;
    L.Icon.Default.mergeOptions({
      iconRetinaUrl: "https://unpkg.com/leaflet@1.7.1/dist/images/marker-icon-2x.png",
      iconUrl: "https://unpkg.com/leaflet@1.7.1/dist/images/marker-icon.png",
      shadowUrl: "https://unpkg.com/leaflet@1.7.1/dist/images/marker-shadow.png",
    });

    setMounted(true);
  }, []);

  if (!mounted || !MapContainer) return <div className="w-full h-[500px] bg-zinc-900 rounded-3xl animate-pulse" />;

  return (
    <div className="relative w-full h-[500px] rounded-3xl overflow-hidden border border-white/5 glass z-0">
      {/* Search Header Overlay */}
      <div className="absolute top-6 left-6 z-[1000] w-64 glass p-4 rounded-2xl border border-white/10 pointer-events-none">
         <h4 className="text-sm font-bold mb-1">Topluluk Haritası: Antalya</h4>
         <p className="text-[10px] text-muted-foreground flex items-center gap-1">
           <Navigation className="w-2 h-2" /> 42 Reels videosundan çıkarıldı
         </p>
      </div>

      {/* Live Leaflet Map */}
      <MapContainer 
        center={[36.8848, 30.7040]} 
        zoom={12} 
        scrollWheelZoom={true} 
        className="w-full h-full z-0"
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
          url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
        />
        
        {MOCK_POINTS.map((point, i) => (
          <Marker key={i} position={[point.lat, point.lng]}>
            <Popup className="custom-popup">
              <div className="p-2 text-zinc-900">
                <p className="font-bold text-sm">{point.title}</p>
                <p className="text-xs">{point.category}</p>
              </div>
            </Popup>
          </Marker>
        ))}
      </MapContainer>

      {/* Google Maps Actions Overlay */}
      <div className="absolute bottom-6 right-6 z-[1000] flex gap-2">
         <button className="bg-[#4285F4] text-white px-5 py-3 rounded-xl flex items-center gap-2 font-bold text-sm shadow-xl shadow-[#4285F4]/20 hover:scale-105 transition-all">
            <img src="https://www.gstatic.com/images/branding/product/2x/maps_96dp.png" className="w-5 h-5" alt="G" />
            Google Maps'te Aç <ExternalLink className="w-4 h-4" />
         </button>
      </div>
    </div>
  );
}
