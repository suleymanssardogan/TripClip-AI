"""OCR text normalization, noise filtering and place candidate extraction."""
import logging
import re as _re
from difflib import SequenceMatcher
from typing import Dict, List, Optional
logger = logging.getLogger(__name__)

class OCRStages:
    def _filter_ocr_pois(self, extracted_texts: List[str], video_id: int) -> List[str]:
        """OCR metinlerinden POI'ları filtrele. OCR başarısızsa boş liste döner."""
        if not extracted_texts:
            return []

        try:
            return self._run_ocr_filter_pipeline(extracted_texts, video_id)
        except Exception as e:
            logger.warning("OCR POI filtresi başarısız — boş liste fallback | %s", e)
            return []

    def _run_ocr_filter_pipeline(self, extracted_texts: List[str], video_id: int) -> List[str]:
        """OCR POI filtresi — gürültü eleme + NER batch + heuristic fallback."""

        tr_lower    = self._tr_lower
        ascii_fold  = self._ascii_fold
        geo_signals = self._geo_signal_set()
        noise_set   = self._noise_pattern_set()
        stopwords   = self._tr_stopword_set()
        generic_set = self._generic_type_set()

        desc_regexes = [
            _re.compile(p, _re.IGNORECASE) for p in [
                r"\d+\s*(yer|tane|adet|durak|mekan|kafe|sahil|plaj)",
                r"\w+['\u2018\u2019]?\s*(?:da|de|ta|te)\s+gezilecek",
                r"(?:da|de|ta|te)\s+gezilecek",
                r"(en iyi|mutlaka|kesinlikle|illa)",
                r"(gidilecek|gorilecek|gorulebilecek)",
                r"(yenilecek|icilecek|icekilecek)",
                r"(nasil|nerede|nereden|hangi)",
                r"(bolum|part|episode|vlog|video)",
                r"\d+\.\s*(bolum|part|video)",
                r"gezilecek",
                r"(listesi|rehberi|onerileri|tavsiyeleri)",
                r"(top\s*\d+|en\s+iyi\s+\d+)",
            ]
        ]

        def _has_geo_signal(text: str) -> bool:
            t_l = tr_lower(text)
            t_f = ascii_fold(t_l)
            return any(s in t_l or ascii_fold(s) in t_f for s in geo_signals)

        def _split_camelcase(t: str) -> str:
            t = _re.sub(r'([a-zğüşıöç])([A-ZĞÜŞİÖÇ])', r'\1 \2', t)
            t = _re.sub(r'([A-ZĞÜŞİÖÇ]{2,})([A-ZĞÜŞİÖÇ][a-zğüşıöç])', r'\1 \2', t)
            return t.strip()

        def _norm(t: str) -> str:
            return _re.sub(r'[^a-z0-9ğüşıöç]', '', tr_lower(t))

        def _is_fuzzy_dup(t: str, seen: list) -> bool:
            norm = _norm(t)
            if len(norm) < 4:
                return False
            return any(
                SequenceMatcher(None, norm, s).ratio() >= 0.82
                for s in seen
            )

        def is_noise(t: str) -> bool:
            t_l  = tr_lower(t).strip()
            t_orig = t.strip()
            if len(t_l) < 4: return True
            if t_l.replace(" ", "").isnumeric(): return True
            if t_l.endswith(("?", "-", ":", ".", ",")): return True
            if t_l.startswith(("-", ".", ":")): return True
            if any(p in t_l for p in noise_set): return True
            if t_l in stopwords: return True
            if "_" in t_orig: return True
            tokens = t_l.split()
            if tokens and tokens[0].isnumeric(): return True
            if any(r.search(t_l) for r in desc_regexes): return True
            short_tokens = [tok for tok in tokens if len(tok) <= 2]
            if tokens and len(short_tokens) / len(tokens) > 0.5: return True
            if t_orig.isupper() and len(t_l) < 6 and len(tokens) == 1: return True
            return False

        # ── Aşama 1: Noise filtresi + fuzzy dedup ────────────────────────────
        candidates, seen_display, seen_norms = [], set(), []
        for t in extracted_texts:
            t_clean = _split_camelcase(t.strip())
            t_lower = tr_lower(t_clean)
            if is_noise(t_clean): continue
            if t_lower in seen_display: continue
            if _is_fuzzy_dup(t_clean, seen_norms): continue
            words = t_clean.split()
            if len(words) == 1 and t_lower in generic_set: continue
            seen_display.add(t_lower)
            seen_norms.append(_norm(t_clean))
            candidates.append(t_clean)

        if not candidates:
            return []

        # ── Aşama 2: Batch NER filtresi ──────────────────────────────────────
        MAX_POIS = 18
        try:
            ner_filtered = self.ner.filter_locations_from_ocr(candidates)
            if ner_filtered:
                logger.info("NER batch: %d → %d POI", len(candidates), len(ner_filtered))
                return ner_filtered[:MAX_POIS]
            # NER 0 sonuç → heuristic fallback
            fallback_pois = [
                t for t in candidates
                if _has_geo_signal(t) or len(t.split()) >= 2
            ][:MAX_POIS]
            logger.info("NER batch 0 sonuç → heuristic fallback: %d POI", len(fallback_pois))
            return fallback_pois
        except Exception as e:
            logger.warning("NER batch OCR filtresi başarısız — heuristic fallback | %s", e)
            return [
                t for t in candidates
                if _has_geo_signal(t) or len(t.split()) >= 2
            ][:MAX_POIS]

    # ─────────────────────────────────────────────────────────────────────────
    # Statik yardımcılar
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _tr_lower(s: str) -> str:
        return s.replace("İ", "i").replace("I", "ı").lower()

    @staticmethod
    def _ascii_fold(s: str) -> str:
        return (s.replace("ğ", "g").replace("ü", "u").replace("ş", "s")
                 .replace("ı", "i").replace("ö", "o").replace("ç", "c")
                 .replace("â", "a").replace("î", "i").replace("û", "u"))

    @staticmethod
    def _geo_signal_set() -> set:
        return {
            "han", "kafe", "cafe", "restoran", "müze", "cami", "kilise",
            "köprü", "kale", "kalesi", "kaleici", "sarayı", "parkı", "gölü",
            "plajı", "plaji", "şelalesi", "selalesi",
            "mağarası", "magarasi", "tepesi", "dağı", "dagi", "vadisi",
            "konak", "çarşı", "carsi", "pazar", "hamam", "türbe", "turbe",
            "anıt", "anit", "kervansaray", "ören",
            "sokağı", "sokagi", "mahallesi", "kapısı", "kapisi",
            "kulesi", "camii", "hamamı", "hamami",
            "bahçesi", "bahcesi", "ormanı", "ormani", "göleti", "barajı",
            "köprüsü", "koprüsü",
            "koyu", "körfez", "korfez", "limanı", "limani",
            "kayalığı", "kayaligi", "adası", "adasi", "yarımadası",
            "kanyonu", "platosu", "çayı", "cayi", "irmağı",
            "yaylası", "yaylasi", "milliparkı",
            "harabeleri", "höyüğü", "hoyugu", "mezarlığı", "mezarligi",
            "kilisesi", "manastırı", "manastiri", "kalıntıları",
            # Yemek & işletme sinyalleri — Gaziantep/şehir lokali içerik
            "yeri", "durumu", "evi", "ocağı", "ocagi", "fırını", "firini",
            "pastanesi", "lokantası", "lokantasi", "kebabçısı", "kebabcisi",
            "büfesi", "bufesi", "dönercisi", "donercisi", "tatlıcısı",
            "çiğköftecisi", "cigkoftecisi", "pidecisi", "lahmacuncusu",
            "muhallebicisi", "baklavacısı", "baklavacisi",
        }

    @staticmethod
    def _noise_pattern_set() -> set:
        return {
            "www.", "http", "@", "#", ".com", ".tr", "₺", "$", "€",
            "follow", "like", "share", "subscribe", "abone", "takip",
        }

    @staticmethod
    def _tr_stopword_set() -> set:
        return {
            "içecek", "yiyecek", "giriş", "çıkış", "bilgi", "lütfen", "teşekkür",
            "devam", "dikkat", "uyarı", "yasak", "serbest", "açık", "kapalı",
            "indirim", "fiyat", "menü", "sipariş", "ödeme", "nakit", "kart",
            "telefon", "adres", "saat", "tarih", "numara", "adet", "toplam",
            "olan", "olur", "oldu", "için", "ile", "veya", "hem", "ama",
            "büyük", "küçük", "yeni", "eski", "güzel", "iyi", "kötü",
            "başka", "diğer", "tüm", "her", "bazı", "çok", "az", "daha",
            "dis", "bis", "ecs", "aci", "bey", "ecek", "acak", "mis",
            "yo", "ve", "da", "de", "ki", "mi", "mu", "mü",
            "kahvesi", "çayı", "kebabı", "mantısı", "baklavası", "köftesi",
            "pidesi", "böreği", "tatlısı", "döneri", "lahmacunu", "çorbası",
            "büfesi", "fırını", "pastanesi", "lokantası", "restoranı",
            "istanbul", "ankara", "izmir",
            "market", "deneme", "gerekenler", "durumu", "masaya", "masasi",
            "lutfen", "yiyecek", "icecek", "siparis", "ucretsiz", "ucret",
            "ntep", "disin", "disi", "bufe", "bufesi",
        }

    @staticmethod
    def _generic_type_set() -> set:
        return {
            "koyu", "koy", "plaj", "plaji", "sahil", "dağ", "dag", "gol", "göl",
            "şelale", "selale", "orman", "vadi", "kanyon", "tepe", "kale",
            "cami", "camii", "köy", "koy", "mahalle", "sokak", "cadde",
            "park", "bahçe", "bahce", "ada", "kıyı", "kiyi", "liman",
        }

    # ─────────────────────────────────────────────────────────────────────────
    # Video işleme (metadata, frame, thumbnail)
    # ─────────────────────────────────────────────────────────────────────────

