"use client";
/* eslint-disable @typescript-eslint/no-explicit-any */

import { ExternalLink, MapPin } from "lucide-react";
import { useEffect, useState } from "react";
import "leaflet/dist/leaflet.css";

let MapContainer: any, TileLayer: any, Marker: any, Popup: any, Polyline: any, L: any;

interface Location {
  original_name: string;
  place_data: {
    name: string;
    location: { lat: number; lng: number };
    type: string;
  };
}

interface Props {
  locations?: Location[];
}

export default function MapPreview({ locations }: Props) {
  const [mounted, setMounted] = useState(false);
  const points = locations ?? [];

  useEffect(() => {
    const initLeaflet = async () => {
      const Leaflet = await import("react-leaflet");
      const LeafletLib = await import("leaflet");
      MapContainer = Leaflet.MapContainer;
      TileLayer = Leaflet.TileLayer;
      Marker = Leaflet.Marker;
      Popup = Leaflet.Popup;
      Polyline = Leaflet.Polyline;
      L = LeafletLib.default || LeafletLib;

      if (L && L.Icon && L.Icon.Default) {
        delete L.Icon.Default.prototype._getIconUrl;
        // unpkg CDN yerine public/leaflet altında bundle edilmiş yerel ikonlar —
        // CDN erişilemezse (offline, kurumsal firewall) haritada işaretçi
        // ikonları kırılmasın diye.
        L.Icon.Default.mergeOptions({
          iconRetinaUrl: "/leaflet/marker-icon-2x.png",
          iconUrl: "/leaflet/marker-icon.png",
          shadowUrl: "/leaflet/marker-shadow.png",
        });
      }
      setTimeout(() => {
        setMounted(true);
      }, 50);
    };
    initLeaflet();
  }, []);

  if (points.length === 0) {
    return (
      <div className="w-full h-full bg-surface2 rounded-md flex flex-col items-center justify-center gap-2 text-text-tertiary">
        <MapPin className="w-6 h-6" />
        <p className="text-xs">Haritada gösterilecek lokasyon yok</p>
      </div>
    );
  }

  if (!mounted || !MapContainer) {
    return <div className="w-full h-full bg-surface2 animate-pulse rounded-md" />;
  }

  const validPoints = points.filter(p => p.place_data?.location?.lat && p.place_data?.location?.lng);
  const center = validPoints.length > 0
    ? [validPoints[0].place_data.location.lat, validPoints[0].place_data.location.lng]
    : [39.0, 35.0];

  const polylinePositions = validPoints.map(p => [p.place_data.location.lat, p.place_data.location.lng]);

  const googleMapsUrl = validPoints.length > 0
    ? `https://www.google.com/maps/dir/${validPoints.map(p => `${p.place_data.location.lat},${p.place_data.location.lng}`).join("/")}`
    : "https://maps.google.com";

  return (
    <div className="relative w-full h-full rounded-xl overflow-hidden z-0">
      <MapContainer
        center={center as [number, number]}
        zoom={validPoints.length > 1 ? 8 : 12}
        scrollWheelZoom={true}
        className="w-full h-full z-0"
      >
        <TileLayer
          attribution='&copy; <a href="https://carto.com/attributions">CARTO</a>'
          url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
        />

        {validPoints.length > 1 && (
          <Polyline positions={polylinePositions} color="#3FD9C4" weight={2} opacity={0.6} dashArray="8,4" />
        )}

        {validPoints.map((point, i) => (
          <Marker key={i} position={[point.place_data.location.lat, point.place_data.location.lng]}>
            <Popup>
              <div className="p-1">
                <p className="font-bold text-sm">{point.original_name}</p>
                <p className="text-xs text-gray-600">{point.place_data.name}</p>
              </div>
            </Popup>
          </Marker>
        ))}
      </MapContainer>

      <div className="absolute bottom-4 right-4 z-[1000]">
        <a
          href={googleMapsUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="bg-[#4285F4] text-white px-4 py-2 rounded-xl flex items-center gap-2 font-bold text-xs shadow-lg hover:scale-105 transition-all"
        >
          Google Maps&apos;te Aç <ExternalLink className="w-3 h-3" />
        </a>
      </div>
    </div>
  );
}
