"""
Infrastructure katmanı — strateji adı → RouteOptimizationStrategy kayıt defteri.

Genişleme noktası: yeni bir strateji (Google Maps API, Apple Maps, OR-Tools,
AI-assisted) eklemek üç adımdır —
  1. `RouteOptimizationStrategy`'yi implemente eden yeni bir sınıf yaz
     (bkz. greedy_distance_strategy.py örneği),
  2. `register_strategy(MyStrategy())` ile burada kaydet,
  3. API/servis katmanında hiçbir şey değişmez — `OptimizeTripRequest.strategy`
     alanına yeni adı geçirmek yeterli.

OptimizationService bu registry dışında hiçbir somut stratejiyi import etmez.
"""
from typing import Dict

from app.domain.optimization.strategy import RouteOptimizationStrategy
from app.infrastructure.optimization.greedy_distance_strategy import GreedyDistanceStrategy

_registry: Dict[str, RouteOptimizationStrategy] = {}


def register_strategy(strategy: RouteOptimizationStrategy) -> None:
    _registry[strategy.name] = strategy


def get_strategy(name: str) -> RouteOptimizationStrategy:
    strategy = _registry.get(name)
    if strategy is None:
        raise KeyError(name)
    return strategy


def available_strategies() -> list[str]:
    return sorted(_registry.keys())


DEFAULT_STRATEGY_NAME = "greedy_distance"
register_strategy(GreedyDistanceStrategy())
