from typing import List, Dict, Tuple
import logging
import math

logger = logging.getLogger(__name__)


class RouteOptimizer:
    """TSP (Traveling Salesman Problem) ile rota optimizasyonu"""

    def haversine_distance(self, lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        """İki koordinat arası mesafeyi km cinsinden hesapla"""
        R = 6371  # Dünya yarıçapı (km)

        lat1, lng1, lat2, lng2 = map(math.radians, [lat1, lng1, lat2, lng2])
        dlat = lat2 - lat1
        dlng = lng2 - lng1

        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng/2)**2
        c = 2 * math.asin(math.sqrt(a))

        return round(R * c, 2)

    def build_distance_matrix(self, locations: List[Dict]) -> List[List[float]]:
        """Tüm lokasyonlar arası mesafe matrisi oluştur"""
        n = len(locations)
        matrix = [[0.0] * n for _ in range(n)]

        for i in range(n):
            for j in range(n):
                if i != j:
                    lat1 = locations[i]["place_data"]["location"]["lat"]
                    lng1 = locations[i]["place_data"]["location"]["lng"]
                    lat2 = locations[j]["place_data"]["location"]["lat"]
                    lng2 = locations[j]["place_data"]["location"]["lng"]
                    matrix[i][j] = self.haversine_distance(lat1, lng1, lat2, lng2)

        logger.info(f"Distance matrix built: {n}x{n}")
        return matrix

    def nearest_neighbor_tsp(self, locations: List[Dict], matrix: List[List[float]]) -> List[Dict]:
        """Nearest neighbor heuristic ile TSP çöz"""
        n = len(locations)
        if n <= 1:
            return locations

        visited = [False] * n
        route_indices = []

        # Başlangıç: ilk lokasyon
        current = 0
        visited[current] = True
        route_indices.append(current)

        for _ in range(n - 1):
            nearest = None
            nearest_dist = float('inf')

            for j in range(n):
                if not visited[j] and matrix[current][j] < nearest_dist:
                    nearest = j
                    nearest_dist = matrix[current][j]

            visited[nearest] = True
            route_indices.append(nearest)
            current = nearest

        route = [locations[i] for i in route_indices]
        logger.info(f"TSP route: {[loc['original_name'] for loc in route]}")
        return route

    def optimize_route(self, enriched_locations: List[Dict]) -> Dict:
        """Ana rota optimizasyon fonksiyonu"""
        if not enriched_locations:
            return {"route": [], "total_distance_km": 0, "stops": 0}

        if len(enriched_locations) == 1:
            return {
                "route": enriched_locations,
                "total_distance_km": 0,
                "stops": 1
            }

        logger.info(f"Optimizing route for {len(enriched_locations)} locations...")

        matrix = self.build_distance_matrix(enriched_locations)
        optimized_route = self.nearest_neighbor_tsp(enriched_locations, matrix)

        # Toplam mesafe hesapla
        total_distance = 0
        for i in range(len(optimized_route) - 1):
            lat1 = optimized_route[i]["place_data"]["location"]["lat"]
            lng1 = optimized_route[i]["place_data"]["location"]["lng"]
            lat2 = optimized_route[i+1]["place_data"]["location"]["lat"]
            lng2 = optimized_route[i+1]["place_data"]["location"]["lng"]
            total_distance += self.haversine_distance(lat1, lng1, lat2, lng2)

        result = {
            "route": optimized_route,
            "total_distance_km": round(total_distance, 2),
            "stops": len(optimized_route)
        }

        logger.info(f"✅ Route optimized: {result['stops']} stops, {result['total_distance_km']}km total")
        return result