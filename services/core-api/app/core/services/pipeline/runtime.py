"""Stage result contract and bounded fallback handling."""
import logging
import time
from dataclasses import dataclass
from concurrent.futures import Future
from typing import Any, Callable, Optional
from app.core.services.pipeline.telemetry import observe_stage
logger = logging.getLogger(__name__)

@dataclass
class ServiceResult:
    """Bir AI servisinin sonucunu ve durumunu tutar."""
    name:          str
    data:          Any
    success:       bool
    fallback_used: bool = False
    error:         Optional[str] = None
    duration_s:    float = 0.0

    @property
    def status_icon(self) -> str:
        if self.success and not self.fallback_used:
            return "✅"
        if self.fallback_used:
            return "⚠️ "
        return "❌"

    def __str__(self) -> str:
        dur = f"{self.duration_s:.1f}s"
        if self.fallback_used:
            return f"{self.status_icon} {self.name:<12} — FALLBACK ({self.error}) [{dur}]"
        if self.success:
            return f"{self.status_icon} {self.name:<12} — OK [{dur}]"
        return f"{self.status_icon} {self.name:<12} — HATA: {self.error} [{dur}]"


def _safe_run(
    name: str,
    fn: Callable,
    fallback: Any,
    *,
    timeout: Optional[float] = None,
    future: Optional[Future] = None,
) -> ServiceResult:
    """
    Bir fonksiyonu veya Future'ı güvenli şekilde çalıştırır.

    Hata durumunda:
      - Exception loglanır
      - fallback değer döner
      - Pipeline durmaz

    Args:
        name:    Servis adı (log ve rapor için)
        fn:      Çağrılacak fonksiyon (future=None ise)
        fallback: Hata durumunda kullanılacak değer
        timeout: future.result() için timeout (saniye)
        future:  Zaten submit edilmiş ThreadPoolExecutor future'ı
    """
    t0 = time.perf_counter()
    try:
        if future is not None:
            data = future.result(timeout=timeout)
        else:
            data = fn()

        dur = time.perf_counter() - t0
        observe_stage(name, dur, "success")
        return ServiceResult(name=name, data=data, success=True, duration_s=dur)

    except TimeoutError:
        dur = time.perf_counter() - t0
        observe_stage(name, dur, "timeout")
        error = f"timeout ({timeout}s)"
        logger.warning("⏰ %s zaman aşımı — fallback kullanılıyor", name)
        return ServiceResult(name=name, data=fallback, success=False,
                             fallback_used=True, error=error, duration_s=dur)

    except Exception as exc:
        dur = time.perf_counter() - t0
        observe_stage(name, dur, "fallback")
        error = type(exc).__name__ + ": " + str(exc)[:120]
        logger.warning("⚠️  %s başarısız — fallback kullanılıyor | %s", name, error)
        return ServiceResult(name=name, data=fallback, success=False,
                             fallback_used=True, error=error, duration_s=dur)


