"use client";

import { Check, MapPin } from "lucide-react";
import type { TripStop } from "@/lib/api";
import { Card } from "@/components/ui/Card";

interface Props {
  stops: TripStop[];
  selectedIds: Set<number>;
  onToggle: (placeId: number) => void;
  onSelectAll: () => void;
  onDeselectAll: () => void;
}

/**
 * Trip'in duraklarından hangilerinin optimize edileceğini seçer — iOS'un
 * `TripOptimizerConfigView.placesSection`'ıyla AYNI semantik: kararlı
 * `place_id`'ler kullanır (dizin/index DEĞİL), varsayılan seçim TÜM
 * duraklar (bkz. `OptimizerConfigForm`'un kendi başlangıç state'i —
 * backend/iOS ile birebir aynı davranış).
 */
export function PlacesSelector({ stops, selectedIds, onToggle, onSelectAll, onDeselectAll }: Props) {
  const allSelected = stops.length > 0 && selectedIds.size === stops.length;

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-[11px] font-bold uppercase tracking-widest text-text-tertiary">
          Mekanlar ({selectedIds.size}/{stops.length} seçili)
        </h3>
        <button
          type="button"
          onClick={allSelected ? onDeselectAll : onSelectAll}
          className="text-xs font-semibold text-accent-text hover:underline"
        >
          {allSelected ? "Seçimi Kaldır" : "Tümünü Seç"}
        </button>
      </div>

      <div className="space-y-2" role="group" aria-label="Optimize edilecek mekanlar">
        {stops.map((stop) => {
          const selected = selectedIds.has(stop.place_id);
          return (
            <Card
              key={stop.place_id}
              className={`p-3 flex items-center gap-3 cursor-pointer transition-colors ${
                selected ? "border-accent/40 bg-accent/5" : "hover:border-border-strong"
              }`}
              role="checkbox"
              aria-checked={selected}
              tabIndex={0}
              onClick={() => onToggle(stop.place_id)}
              onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onToggle(stop.place_id); } }}
            >
              <div
                className={`w-5 h-5 rounded-full border flex items-center justify-center shrink-0 ${
                  selected ? "bg-accent border-accent" : "border-border-strong"
                }`}
                aria-hidden="true"
              >
                {selected && <Check className="w-3 h-3 text-on-accent" strokeWidth={3} />}
              </div>
              <MapPin className="w-4 h-4 text-text-tertiary shrink-0" aria-hidden="true" />
              <div className="min-w-0">
                <p className="text-sm font-medium text-text truncate">{stop.name}</p>
                {stop.city && <p className="text-xs text-text-tertiary truncate">{stop.city}</p>}
              </div>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
