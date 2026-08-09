"""
Infrastructure katmanı — strateji adı → RouteOptimizationStrategy kayıt defteri.

Genişleme noktası: yeni bir strateji (Google Maps API, Apple Maps,
AI-assisted, ...) eklemek üç adımdır — `ortools_strategy.py` bu deseni
kanıtlayan ikinci gerçek implementasyon:
  1. `RouteOptimizationStrategy`'yi implemente eden yeni bir sınıf yaz
     (bkz. greedy_distance_strategy.py / ortools_strategy.py örnekleri),
  2. `register_strategy(MyStrategy())` ile burada kaydet,
  3. API/servis katmanında hiçbir şey değişmedi (bu milestone'un kanıtladığı
     tam olarak bu) — `OptimizeTripRequest.strategy` alanına yeni adı
     geçirmek yeterli.

OptimizationService bu registry dışında hiçbir somut stratejiyi import etmez.
"""
from typing import Dict

from app.domain.optimization.strategy import RouteOptimizationStrategy
from app.infrastructure.optimization.greedy_distance_strategy import GreedyDistanceStrategy
from app.infrastructure.optimization.ortools_strategy import ORToolsRouteOptimizationStrategy

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
register_strategy(ORToolsRouteOptimizationStrategy())
