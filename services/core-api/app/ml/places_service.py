import requests
from typing import List,Dict,Optional
import logging
import time

logger = logging.getLogger(__name__)

class PlacesService:
    """Nominatim(OpensStreetMap) for location enrichment"""

    def __init__(self):
        self.base_url = "https://nominatim.openstreetmap.org"
        self.headers= {
            "User-Agent": "TripClip-AI/1.0 (educational project - github.com/suleymanssardogan/TripClip-AI)"
            
        }
        logger.info("Nominatim service initialized")
    
    def search_place(self,location_name:str,country:str="Turkey") ->Optional[Dict]:
        """Search for a place using Nominatim"""

        try:
            #Rate limitin: 1 request/second(Nominatim requirement)
            time.sleep(1)

            params ={
                "q":f"{location_name},{country}",
                "format":"json",
                "limit":1,
                "addressdetails":1
            }
            response = requests.get(
                f"{self.base_url}/search",
                params=params,
                headers=self.headers,
                timeout=10
            )
            if response.status_code!=200:
                logger.error(f"Nominatim error: {response.status_code}")
                return None
            results =response.json()
            if not results:
                logger.info(f"No results for: {location_name}")
                return None
            #First Result
            place = results[0]

            #Exract Data
            place_data = {
                "name": place.get("display_name"),
                "place_id": place.get("place_id"),
                "osm_id": place.get("osm_id"),
                "osm_type": place.get("osm_type"),
                "address": place.get("display_name"),
                "location": {
                    "lat": float(place.get("lat")),
                    "lng": float(place.get("lon"))
                },
                "type": place.get("type"),
                "class": place.get("class"),
                "importance": place.get("importance"),
                "address_details": place.get("address", {})
            }
            logger.info(f"Found: {place.get('display_name')}")
            return place_data
            
        except requests.Timeout:
            logger.error(f"Nominatim timeout for: {location_name}")
            return None
        except Exception as e:
            logger.error(f"Nominatim search error for '{location_name}': {e}")
            return None
    def enrich_locations(self, locations: List[str]) -> List[Dict]:
        """Enrich location names with Nominatim data"""
        
        if not locations:
            logger.warning("No locations to enrich")
            return []
        
        enriched = []
        
        for location in locations:
            # Skip invalid locations (tokenization artifacts)
            if location.startswith("##") or len(location) < 3:
                logger.info(f"Skipping invalid location: {location}")
                continue
            
            place_data = self.search_place(location)
            
            if place_data:
                enriched.append({
                    "original_name": location,
                    "place_data": place_data
                })
        
        logger.info(f" Enriched {len(enriched)}/{len(locations)} locations")
        return enriched