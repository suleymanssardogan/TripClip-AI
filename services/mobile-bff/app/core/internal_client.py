"""
Core-API'ye giden istekler için ortak httpx client factory.

INTERNAL_API_SECRET ayarlıysa her istekte X-Internal-Secret header'ı eklenir —
Docker network izolasyonunun ötesinde bir savunma katmanı: core-api'nin
/internal/* route'ları bu secret'ı doğrular, böylece ağ yanlış yapılandırılsa
bile core-api'ye doğrudan (BFF'i atlayarak) x-user-id sahteciliği yapılamaz.

INTERNAL_API_SECRET tanımlı değilse (örn. local geliştirme) sessizce atlanır —
mevcut davranış bozulmaz.
"""
import os
import httpx

INTERNAL_API_SECRET = os.getenv("INTERNAL_API_SECRET", "")


def internal_client(timeout: float) -> httpx.AsyncClient:
    """core-api'ye istek atmak için kullanılacak httpx client — secret header dahil."""
    headers = {"X-Internal-Secret": INTERNAL_API_SECRET} if INTERNAL_API_SECRET else {}
    return httpx.AsyncClient(timeout=timeout, headers=headers)
