"""
Domain katmanı — Route optimization strateji arayüzü.

Bu, spesifikasyonun "Design the optimizer behind an interface so different
strategies can be plugged in later" gereksiniminin genişleme noktası:
GreedyDistanceStrategy bugünkü tek implementasyon, ama Google Maps/Apple
Maps/OR-Tools/AI-assisted stratejileri aynı arayüzü uygulayarak
`strategy_registry`'ye eklenebilir — OptimizationService hiçbiri hakkında
bilgi sahibi değildir, yalnızca bu arayüzle konuşur.
"""
from abc import ABC, abstractmethod
from typing import List

from app.domain.optimization.models import (
    PlaceInput,
    OptimizationConstraints,
    OptimizationResult,
)


class RouteOptimizationStrategy(ABC):

    @property
    @abstractmethod
    def name(self) -> str:
        """Registry anahtarı ve persist edilen `strategy_name` — örn. 'greedy_distance'."""
        ...

    @abstractmethod
    def optimize(
        self,
        places: List[PlaceInput],
        constraints: OptimizationConstraints,
    ) -> OptimizationResult:
        """
        `places` zaten tekilleştirilmiş ve kullanıcının kütüphanesine ait
        olduğu doğrulanmış olmalı (bkz. OptimizationService) — strateji
        yalnızca sıralama/zamanlama/gün dağılımı sorumluluğunu taşır,
        yetkilendirme ya da sahiplik kontrolü yapmaz.
        """
        ...
