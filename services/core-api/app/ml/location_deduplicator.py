from typing import List, Dict
import logging
import math

logger = logging.getLogger(__name__)

class LocationDeduplicator:
    """Deduplicate enriched locations based on coordinates"""
    
    def __init__(self, distance_threshold_km: float = 5.0):
        """
        Args:
            distance_threshold_km: Locations within this distance are considered duplicates
        """
        self.distance_threshold = distance_threshold_km
        logger.info(f"✅ LocationDeduplicator initialized (threshold: {distance_threshold_km}km)")
    
    def calculate_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        Calculate distance between two coordinates using Haversine formula
        Returns distance in kilometers
        """
        # Earth radius in kilometers
        R = 6371.0
        
        # Convert to radians
        lat1_rad = math.radians(lat1)
        lon1_rad = math.radians(lon1)
        lat2_rad = math.radians(lat2)
        lon2_rad = math.radians(lon2)
        
        # Haversine formula
        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad
        
        a = math.sin(dlat / 2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        distance = R * c
        return distance
    
    def deduplicate_locations(self, enriched_locations: List[Dict]) -> List[Dict]:
        """
        Remove duplicate locations based on coordinate proximity
        Keeps the location with higher importance score
        """
        if not enriched_locations or len(enriched_locations) <= 1:
            return enriched_locations
        
        deduplicated = []
        seen_coords = []
        
        # Sort by importance (if available)
        sorted_locations = sorted(
            enriched_locations,
            key=lambda x: x.get('place_data', {}).get('importance', 0),
            reverse=True
        )
        
        for location in sorted_locations:
            place_data = location.get('place_data', {})
            location_coords = place_data.get('location', {})
            
            lat = location_coords.get('lat')
            lng = location_coords.get('lng')
            
            if not lat or not lng:
                logger.warning(f"Location missing coordinates: {location.get('original_name')}")
                continue
            
            # Check if this location is too close to any already added
            is_duplicate = False
            
            for seen_lat, seen_lng in seen_coords:
                distance = self.calculate_distance(lat, lng, seen_lat, seen_lng)
                
                if distance < self.distance_threshold:
                    logger.info(
                        f"Duplicate found: {location.get('original_name')} "
                        f"(distance: {distance:.2f}km from existing location)"
                    )
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                deduplicated.append(location)
                seen_coords.append((lat, lng))
        
        logger.info(f"✅ Deduplication: {len(enriched_locations)} → {len(deduplicated)} locations")
        return deduplicated
    
    def get_location_summary(self, enriched_locations: List[Dict]) -> Dict:
        """Generate summary of unique locations"""
        
        deduplicated = self.deduplicate_locations(enriched_locations)
        
        summary = {
            "total_locations": len(deduplicated),
            "locations": []
        }
        
        for loc in deduplicated:
            place_data = loc.get('place_data', {})
            coords = place_data.get('location', {})
            
            summary["locations"].append({
                "name": loc.get('original_name'),
                "full_name": place_data.get('name'),
                "coordinates": {
                    "lat": coords.get('lat'),
                    "lng": coords.get('lng')
                },
                "type": place_data.get('type'),
                "importance": place_data.get('importance')
            })
        
        return summary