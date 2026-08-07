"""
TripShare/TripCollaborator arasında paylaşılan enum'lar — bilerek ayrı bir
modülde: bu dosyanın hiçbir DB bağımlılığı (app.core.database import'u) yok,
bu yüzden iki model birbirinden import ederken database.py'nin model-kayıt
satırı üzerinden oluşan dairesel import'a düşmüyor (her model dosyası Base'i
database.py'den alıyor, database.py da tüm modelleri tek satırda import
ediyor — iki model doğrudan birbirini import ederse bu döngüye girer).
"""
import enum


class ShareStatus(str, enum.Enum):
    PENDING  = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    EXPIRED  = "expired"
    REVOKED  = "revoked"


class CollaboratorRole(str, enum.Enum):
    VIEWER = "viewer"
    EDITOR = "editor"
